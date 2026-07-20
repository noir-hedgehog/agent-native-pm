/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Network } from "lucide-react";
import { LabelPropertyIcon } from "@plane/propel/icons";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useLabel } from "@/hooks/store/use-label";

export type TWorkItemAdditionalSidebarProperties = {
  workItemId: string;
  workItemTypeId: string | null;
  projectId: string;
  workspaceSlug: string;
  isEditable: boolean;
  isPeekView?: boolean;
};

const KINDS = ["requirement", "bug", "task", "analysis"] as const;

export const WorkItemAdditionalSidebarProperties = observer(
  function WorkItemAdditionalSidebarProperties(props: TWorkItemAdditionalSidebarProperties) {
    const { isEditable, projectId, workspaceSlug, workItemId } = props;
    const {
      issue: { getIssueById, updateIssue },
    } = useIssueDetail();
    const { fetchProjectLabels, getProjectLabels } = useLabel();
    const issue = getIssueById(workItemId);
    const labels = getProjectLabels(projectId);

    useEffect(() => {
      if (!labels) void fetchProjectLabels(workspaceSlug, projectId);
    }, [fetchProjectLabels, labels, projectId, workspaceSlug]);

    if (!issue) return null;
    const kindLabels = (labels ?? []).filter((label) =>
      label.name.toLowerCase().startsWith("kind:"),
    );
    const current = kindLabels.find((label) => issue.label_ids?.includes(label.id));
    const [runtime, setRuntime] = useState<{
      status: string;
      current_node_id: string;
      stages?: Array<{
        assigned_agent_id: string | null;
        attempts: Array<{ provider: string; model: string; cost: string; evidence: unknown[] }>;
      }>;
    } | null>(null);

    useEffect(() => {
      let active = true;
      const base = `/api/workspaces/${workspaceSlug}/projects/${projectId}/mesh/runs`;
      void fetch(`${base}/`, { credentials: "include" })
        .then((response) => response.json())
        .then(async (payload) => {
          const run = payload.runs?.find(
            (item: { work_item_id: string }) => item.work_item_id === workItemId,
          );
          if (!run) return null;
          const details = await fetch(`${base}/${run.id}/`, { credentials: "include" }).then(
            (response) => response.json(),
          );
          return details.run;
        })
        .then((value) => active && setRuntime(value))
        .catch(() => active && setRuntime(null));
      return () => {
        active = false;
      };
    }, [projectId, workItemId, workspaceSlug]);

    const updateKind = async (kind: string) => {
      const selected = kindLabels.find((label) => label.name.toLowerCase() === `kind:${kind}`);
      if (!selected) return;
      const kindIds = new Set(kindLabels.map((label) => label.id));
      const nextLabels = [...(issue.label_ids ?? []).filter((id) => !kindIds.has(id)), selected.id];
      await updateIssue(workspaceSlug, projectId, workItemId, { label_ids: nextLabels });
    };

    const latestStage = runtime?.stages?.at(-1);
    const latestAttempt = latestStage?.attempts?.at(-1);

    return (
      <>
        <SidebarPropertyListItem icon={LabelPropertyIcon} label="Work item kind">
          <select
            className="h-7.5 w-full grow rounded-sm bg-transparent px-2 text-body-xs-regular text-primary outline-none disabled:text-placeholder"
            value={current?.name.split(":", 2)[1] ?? ""}
            disabled={!isEditable || kindLabels.length === 0}
            onChange={(event) => void updateKind(event.target.value)}
            aria-label="Work item kind"
          >
            <option value="" disabled>
              None
            </option>
            {KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind[0].toUpperCase() + kind.slice(1)}
              </option>
            ))}
          </select>
        </SidebarPropertyListItem>
        {runtime && (
          <SidebarPropertyListItem icon={Network} label="Mesh runtime">
            <div className="flex w-full min-w-0 flex-col px-2 py-1 text-11">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-primary">
                  {runtime.current_node_id || "Complete"}
                </span>
                <span className="text-secondary">{runtime.status}</span>
              </div>
              {(latestStage?.assigned_agent_id || latestAttempt) && (
                <div className="mt-0.5 truncate text-tertiary">
                  {latestStage?.assigned_agent_id || "Unassigned"}
                  {latestAttempt
                    ? ` / ${latestAttempt.provider}:${latestAttempt.model} / ${latestAttempt.cost}`
                    : ""}
                </div>
              )}
            </div>
          </SidebarPropertyListItem>
        )}
      </>
    );
  },
);
