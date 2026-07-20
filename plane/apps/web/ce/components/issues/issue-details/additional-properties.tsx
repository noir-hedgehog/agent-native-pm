/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
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

export const WorkItemAdditionalSidebarProperties = observer(function WorkItemAdditionalSidebarProperties(
  props: TWorkItemAdditionalSidebarProperties
) {
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
  const kindLabels = (labels ?? []).filter((label) => label.name.toLowerCase().startsWith("kind:"));
  const current = kindLabels.find((label) => issue.label_ids?.includes(label.id));

  const updateKind = async (kind: string) => {
    const selected = kindLabels.find((label) => label.name.toLowerCase() === `kind:${kind}`);
    if (!selected) return;
    const kindIds = new Set(kindLabels.map((label) => label.id));
    const nextLabels = [...(issue.label_ids ?? []).filter((id) => !kindIds.has(id)), selected.id];
    await updateIssue(workspaceSlug, projectId, workItemId, { label_ids: nextLabels });
  };

  return (
    <SidebarPropertyListItem icon={LabelPropertyIcon} label="Work item kind">
      <select
        className="h-7.5 w-full grow rounded-sm bg-transparent px-2 text-body-xs-regular text-primary outline-none disabled:text-placeholder"
        value={current?.name.split(":", 2)[1] ?? ""}
        disabled={!isEditable || kindLabels.length === 0}
        onChange={(event) => void updateKind(event.target.value)}
        aria-label="Work item kind"
      >
        <option value="" disabled>None</option>
        {KINDS.map((kind) => <option key={kind} value={kind}>{kind[0].toUpperCase() + kind.slice(1)}</option>)}
      </select>
    </SidebarPropertyListItem>
  );
});
