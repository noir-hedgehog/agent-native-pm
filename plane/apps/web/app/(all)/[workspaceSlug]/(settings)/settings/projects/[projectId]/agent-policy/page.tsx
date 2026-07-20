/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Check, RefreshCcw, Save, X } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Input, TextArea } from "@plane/ui";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { AgentPolicyProjectSettingsHeader } from "./header";

type TProjectPolicy = {
  policy_id?: string;
  project_id: string;
  version?: number;
  pipeline_definition: string[];
  agent_profile_by_role: Record<string, string>;
  transition_approval_rules: Record<string, boolean>;
  transition_timeout_hours: {
    reminder: number;
    block: number;
  };
  allowed_actions_by_role: Record<string, string[]>;
  published_by: string;
  change_note?: string | null;
  created_at?: string;
};

type TRuntimeSession = {
  task_session_id: string;
  task_id: string;
  status: string;
  updated_at: string;
  runs: Array<{ agent_run_id: string; stage_role: string; agent_profile: string; status: string }>;
  pending_approval?: { approval_id: string; to_stage_role: string; created_at: string } | null;
};

const DEFAULT_ACTIONS = "read_plane,comment,update_status,create_work_item";
const DEFAULT_PIPELINE = "coder\ntester\nreviewer";

function splitLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitCsv(value: string) {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function parseKeyValueLines(value: string) {
  return splitLines(value).reduce<Record<string, string>>((acc, line) => {
    const [key, ...rest] = line.split("=");
    if (key?.trim() && rest.length > 0) acc[key.trim()] = rest.join("=").trim();
    return acc;
  }, {});
}

function parseActionsByRole(value: string) {
  return splitLines(value).reduce<Record<string, string[]>>((acc, line) => {
    const [role, ...rest] = line.split("=");
    if (role?.trim() && rest.length > 0) acc[role.trim()] = splitCsv(rest.join("="));
    return acc;
  }, {});
}

function stringifyRoleMap(value: Record<string, string>) {
  return Object.entries(value)
    .map(([role, agent]) => `${role}=${agent}`)
    .join("\n");
}

function stringifyActionsByRole(value: Record<string, string[]>) {
  return Object.entries(value)
    .map(([role, actions]) => `${role}=${actions.join(",")}`)
    .join("\n");
}

function transitionKeysFor(roles: string[]) {
  return roles.map((role, index) => `${role}->${roles[index + 1] ?? "done"}`);
}

function defaultPolicy(projectId: string): TProjectPolicy {
  const roles = splitLines(DEFAULT_PIPELINE);
  return {
    project_id: projectId,
    pipeline_definition: roles,
    agent_profile_by_role: Object.fromEntries(roles.map((role) => [role, "iris"])),
    transition_approval_rules: Object.fromEntries(
      transitionKeysFor(roles).map((key) => [key, false]),
    ),
    transition_timeout_hours: { reminder: 24, block: 72 },
    allowed_actions_by_role: Object.fromEntries(
      roles.map((role) => [role, splitCsv(DEFAULT_ACTIONS)]),
    ),
    published_by: "plane-admin",
    change_note: "",
  };
}

function AgentPolicySettingsPage({
  params,
}: {
  params: { projectId: string; workspaceSlug: string };
}) {
  const { projectId, workspaceSlug } = params;
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentProjectDetails: projectDetails } = useProject();
  const canPerformProjectAdminActions = allowPermissions(
    [EUserPermissions.ADMIN],
    EUserPermissionsLevel.PROJECT,
  );

  const [pipelineText, setPipelineText] = useState(DEFAULT_PIPELINE);
  const [agentMapText, setAgentMapText] = useState("");
  const [approvalText, setApprovalText] = useState("");
  const [actionsText, setActionsText] = useState("");
  const [reminderHours, setReminderHours] = useState("24");
  const [blockHours, setBlockHours] = useState("72");
  const [publishedBy, setPublishedBy] = useState("plane-admin");
  const [changeNote, setChangeNote] = useState("");
  const [latestVersion, setLatestVersion] = useState<number | null>(null);
  const [history, setHistory] = useState<TProjectPolicy[]>([]);
  const [runtimeSessions, setRuntimeSessions] = useState<TRuntimeSession[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState<Record<string, string>>({});
  const [decidingApprovalId, setDecidingApprovalId] = useState<string | null>(null);
  const policyApiUrl = `/api/workspaces/${encodeURIComponent(workspaceSlug)}/projects/${projectId}/agent-policy`;

  const pipelineRoles = useMemo(() => splitLines(pipelineText), [pipelineText]);
  const availableTransitions = useMemo(() => transitionKeysFor(pipelineRoles), [pipelineRoles]);
  const historyNewestFirst = useMemo(() => {
    const rows: TProjectPolicy[] = [];
    for (let index = history.length - 1; index >= 0; index -= 1) rows.push(history[index]);
    return rows;
  }, [history]);

  const loadPolicy = useCallback(async () => {
    setIsLoading(true);
    try {
      const [latestResponse, historyResponse, runtimeResponse] = await Promise.all([
        fetch(`${policyApiUrl}/`, { credentials: "include" }),
        fetch(`${policyApiUrl}/history/`, { credentials: "include" }),
        fetch(`${policyApiUrl}/runtime/`, { credentials: "include" }),
      ]);

      if (latestResponse.ok) {
        const { policy } = (await latestResponse.json()) as { policy: TProjectPolicy };
        setPipelineText(policy.pipeline_definition.join("\n"));
        setAgentMapText(stringifyRoleMap(policy.agent_profile_by_role));
        setApprovalText(
          Object.entries(policy.transition_approval_rules)
            .filter(([, required]) => required)
            .map(([key]) => key)
            .join("\n"),
        );
        setActionsText(stringifyActionsByRole(policy.allowed_actions_by_role));
        setReminderHours(String(policy.transition_timeout_hours.reminder));
        setBlockHours(String(policy.transition_timeout_hours.block));
        setPublishedBy(policy.published_by || "plane-admin");
        setChangeNote(policy.change_note || "");
        setLatestVersion(policy.version ?? null);
      } else if (latestResponse.status === 404) {
        const policy = defaultPolicy(projectId);
        setPipelineText(policy.pipeline_definition.join("\n"));
        setAgentMapText(stringifyRoleMap(policy.agent_profile_by_role));
        setApprovalText("");
        setActionsText(stringifyActionsByRole(policy.allowed_actions_by_role));
        setReminderHours(String(policy.transition_timeout_hours.reminder));
        setBlockHours(String(policy.transition_timeout_hours.block));
        setPublishedBy(policy.published_by);
        setChangeNote("");
        setLatestVersion(null);
      } else {
        throw new Error("Failed to load policy");
      }

      if (historyResponse.ok) {
        const { policies } = (await historyResponse.json()) as { policies: TProjectPolicy[] };
        setHistory(policies);
      }
      if (runtimeResponse.ok) {
        const { sessions } = (await runtimeResponse.json()) as { sessions: TRuntimeSession[] };
        setRuntimeSessions(sessions);
      }
    } catch (error) {
      console.error(error);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error",
        message: "Agent policy could not be loaded.",
      });
    } finally {
      setIsLoading(false);
    }
  }, [policyApiUrl, projectId]);

  useEffect(() => {
    loadPolicy();
  }, [loadPolicy]);

  const buildPayload = () => {
    const roles = splitLines(pipelineText);
    const agentMap = parseKeyValueLines(agentMapText);
    const selectedApprovals = new Set(splitLines(approvalText));
    const actionsByRole = parseActionsByRole(actionsText);

    return {
      pipeline_definition: roles,
      agent_profile_by_role: agentMap,
      transition_approval_rules: Object.fromEntries(
        transitionKeysFor(roles).map((key) => [key, selectedApprovals.has(key)]),
      ),
      transition_timeout_hours: {
        reminder: Number(reminderHours),
        block: Number(blockHours),
      },
      allowed_actions_by_role: actionsByRole,
      published_by: publishedBy.trim() || "plane-admin",
      change_note: changeNote.trim() || null,
    };
  };

  const handlePublish = async () => {
    setIsSaving(true);
    try {
      const response = await fetch(`${policyApiUrl}/`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.error?.message || "Policy publish failed");

      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Saved",
        message: "Agent policy published.",
      });
      await loadPolicy();
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error",
        message: error instanceof Error ? error.message : "Policy publish failed.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleApprovalDecision = async (approvalId: string, decision: "approve" | "reject") => {
    const note = decisionNotes[approvalId]?.trim() || "";
    if (decision === "reject" && !note) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Decision note required",
        message: "Add a reason before rejecting.",
      });
      return;
    }
    setDecidingApprovalId(approvalId);
    try {
      const response = await fetch(`${policyApiUrl}/approvals/${approvalId}/`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, note: note || null }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.error?.message || "Approval decision failed");
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: decision === "approve" ? "Pipeline resumed" : "Pipeline blocked",
        message:
          decision === "approve"
            ? "The next Agent stage has been queued."
            : "The execution was rejected.",
      });
      await loadPolicy();
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Decision failed",
        message: error instanceof Error ? error.message : "Approval decision failed.",
      });
    } finally {
      setDecidingApprovalId(null);
    }
  };

  const pageTitle = projectDetails?.name ? `${projectDetails.name} - Agent Policy` : "Agent Policy";

  if (workspaceUserInfo && !canPerformProjectAdminActions) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<AgentPolicyProjectSettingsHeader />} hugging>
      <PageHead title={pageTitle} />
      <section className="w-full">
        <SettingsHeading
          title="Agent Policy"
          description="Project-level agent workflow and permissions."
        />

        <div className="mt-6 space-y-8">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <label htmlFor="agent-policy-pipeline" className="space-y-2">
              <span className="text-sm font-medium text-primary">Pipeline roles</span>
              <TextArea
                id="agent-policy-pipeline"
                value={pipelineText}
                onChange={(event) => setPipelineText(event.target.value)}
                className="font-mono min-h-28 text-13"
              />
            </label>

            <label htmlFor="agent-policy-agent-map" className="space-y-2">
              <span className="text-sm font-medium text-primary">Role to agent</span>
              <TextArea
                id="agent-policy-agent-map"
                value={agentMapText}
                onChange={(event) => setAgentMapText(event.target.value)}
                className="font-mono min-h-28 text-13"
              />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <label htmlFor="agent-policy-approvals" className="space-y-2">
              <span className="text-sm font-medium text-primary">Approval gates</span>
              <TextArea
                id="agent-policy-approvals"
                value={approvalText}
                onChange={(event) => setApprovalText(event.target.value)}
                placeholder={availableTransitions.join("\n")}
                className="font-mono min-h-24 text-13"
              />
            </label>

            <label htmlFor="agent-policy-actions" className="space-y-2">
              <span className="text-sm font-medium text-primary">Allowed actions</span>
              <TextArea
                id="agent-policy-actions"
                value={actionsText}
                onChange={(event) => setActionsText(event.target.value)}
                className="font-mono min-h-24 text-13"
              />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <label htmlFor="agent-policy-reminder-hours" className="space-y-2">
              <span className="text-sm font-medium text-primary">Reminder hours</span>
              <Input
                id="agent-policy-reminder-hours"
                type="number"
                min={1}
                value={reminderHours}
                onChange={(event) => setReminderHours(event.target.value)}
              />
            </label>
            <label htmlFor="agent-policy-block-hours" className="space-y-2">
              <span className="text-sm font-medium text-primary">Block hours</span>
              <Input
                id="agent-policy-block-hours"
                type="number"
                min={2}
                value={blockHours}
                onChange={(event) => setBlockHours(event.target.value)}
              />
            </label>
            <label htmlFor="agent-policy-published-by" className="space-y-2">
              <span className="text-sm font-medium text-primary">Published by</span>
              <Input
                id="agent-policy-published-by"
                value={publishedBy}
                disabled
                onChange={(event) => setPublishedBy(event.target.value)}
              />
            </label>
            <label htmlFor="agent-policy-change-note" className="space-y-2">
              <span className="text-sm font-medium text-primary">Change note</span>
              <Input
                id="agent-policy-change-note"
                value={changeNote}
                onChange={(event) => setChangeNote(event.target.value)}
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-subtle-1 pt-4">
            <div className="text-sm text-secondary">
              {latestVersion ? `Current version ${latestVersion}` : "No published policy"}
              {isLoading ? " · Loading" : ""}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={loadPolicy} disabled={isLoading || isSaving}>
                <RefreshCcw className="mr-2 size-4" />
                Reload
              </Button>
              <Button
                variant="primary"
                onClick={handlePublish}
                loading={isSaving}
                disabled={isLoading}
              >
                <Save className="mr-2 size-4" />
                Publish policy
              </Button>
            </div>
          </div>

          <div className="border-t border-subtle-1 pt-4">
            <h3 className="text-sm font-medium text-primary">Active execution</h3>
            <div className="mt-3 overflow-hidden border-y border-subtle-1">
              {runtimeSessions.length === 0 ? (
                <div className="px-3 py-3 text-sm text-secondary">
                  No Mesh execution has been recorded for this project.
                </div>
              ) : (
                runtimeSessions.slice(0, 10).map((session) => (
                  <div
                    key={session.task_session_id}
                    className="flex flex-wrap items-center justify-between gap-3 border-b border-subtle-1 px-3 py-2 last:border-b-0"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-primary">
                        {session.task_id}
                      </div>
                      <div className="text-11 text-secondary">
                        {session.runs
                          .map((run) => `${run.stage_role}:${run.agent_profile}`)
                          .join(" → ") || "Waiting for first run"}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2 text-12">
                      {session.pending_approval && (
                        <>
                          <span className="text-warning-primary">
                            Approval → {session.pending_approval.to_stage_role}
                          </span>
                          <Input
                            className="h-8 w-48"
                            placeholder="Decision note"
                            value={decisionNotes[session.pending_approval.approval_id] || ""}
                            onChange={(event) =>
                              setDecisionNotes((current) => ({
                                ...current,
                                [session.pending_approval!.approval_id]: event.target.value,
                              }))
                            }
                          />
                          <button
                            type="button"
                            className="grid size-8 place-items-center rounded text-success-primary hover:bg-success-primary/10 disabled:opacity-50"
                            title="Approve and resume"
                            aria-label="Approve and resume"
                            disabled={decidingApprovalId === session.pending_approval.approval_id}
                            onClick={() =>
                              void handleApprovalDecision(
                                session.pending_approval!.approval_id,
                                "approve",
                              )
                            }
                          >
                            <Check className="size-4" />
                          </button>
                          <button
                            type="button"
                            className="grid size-8 place-items-center rounded text-danger-primary hover:bg-danger-primary/10 disabled:opacity-50"
                            title="Reject and block"
                            aria-label="Reject and block"
                            disabled={decidingApprovalId === session.pending_approval.approval_id}
                            onClick={() =>
                              void handleApprovalDecision(
                                session.pending_approval!.approval_id,
                                "reject",
                              )
                            }
                          >
                            <X className="size-4" />
                          </button>
                        </>
                      )}
                      <span className="rounded-sm bg-surface-2 px-2 py-1 text-secondary">
                        {session.status}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="border-t border-subtle-1 pt-4">
            <h3 className="text-sm font-medium text-primary">Version history</h3>
            <div className="mt-3 divide-y divide-subtle-1 rounded-md border border-subtle-1">
              {history.length === 0 ? (
                <div className="text-sm px-3 py-3 text-secondary">No versions yet.</div>
              ) : (
                historyNewestFirst.map((policy) => (
                  <div
                    key={policy.policy_id || policy.version}
                    className="text-sm flex flex-wrap items-center justify-between gap-3 px-3 py-2"
                  >
                    <span className="font-medium text-primary">v{policy.version}</span>
                    <span className="text-secondary">{policy.change_note || "No note"}</span>
                    <span className="text-tertiary">{policy.created_at || ""}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </section>
    </SettingsContentWrapper>
  );
}

export default observer(AgentPolicySettingsPage);
