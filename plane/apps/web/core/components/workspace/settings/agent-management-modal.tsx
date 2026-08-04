/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { type FormEvent, useState } from "react";
import useSWR, { mutate } from "swr";
import { Bot, Check, RefreshCw, Settings2, X } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IApiToken } from "@plane/types";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { GeneratedTokenDetails } from "@/components/api-token/modal/generated-token-details";
import { WorkspaceService } from "@/services/workspace.service";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onAgentCreated: () => Promise<unknown>;
  workspaceSlug: string;
};

type Application = {
  id: string;
  agent_id: string;
  display_name: string;
  email: string;
  requested_role: "admin" | "member" | "guest";
  reason: string;
  agent_type: string;
  runtime_provider: string;
  capability_claims: string[];
  boundaries: { denied_capabilities?: string[] };
};

type WorkspaceAgent = {
  workspace_member_id: string;
  agent_id: string;
  display_name: string;
  role: number;
  is_active: boolean;
  agent_profile: {
    agent_type: string;
    runtime_provider: string;
    endpoint_url: string;
    status: string;
    trust_level: string;
    agent_card: { available?: boolean; sync_error?: string };
    capability_claims: string[];
    boundaries: { denied_capabilities?: string[] };
  } | null;
  default_execution: {
    provider: string;
    model: string;
    configuration_version: number;
    has_secret_reference: boolean;
    settings: Record<string, unknown>;
    is_active: boolean;
  } | null;
};

const workspaceService = new WorkspaceService();

export function AgentManagementModal({ isOpen, onAgentCreated, onClose, workspaceSlug }: Props) {
  const [mode, setMode] = useState<"agents" | "create" | "applications">("agents");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentId, setAgentId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [agentType, setAgentType] = useState("autonomous");
  const [runtimeProvider, setRuntimeProvider] = useState("custom");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [defaultModel, setDefaultModel] = useState("");
  const [secretReference, setSecretReference] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const [deniedCapabilities, setDeniedCapabilities] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [generatedToken, setGeneratedToken] = useState<IApiToken | null>(null);
  const applicationsKey = `AGENT_APPLICATIONS_${workspaceSlug}`;
  const agentsKey = `WORKSPACE_AGENTS_${workspaceSlug}`;
  const { data: applications, isLoading } = useSWR<Application[]>(isOpen ? applicationsKey : null, () =>
    workspaceService.listAgentApplications(workspaceSlug)
  );
  const { data: agents, isLoading: agentsLoading } = useSWR<WorkspaceAgent[]>(isOpen ? agentsKey : null, () =>
    workspaceService.listWorkspaceAgents(workspaceSlug)
  );

  const reset = () => {
    setAgentId("");
    setDisplayName("");
    setEmail("");
    setRole("member");
    setAgentType("autonomous");
    setRuntimeProvider("custom");
    setEndpointUrl("");
    setDefaultModel("");
    setSecretReference("");
    setCapabilities("");
    setDeniedCapabilities("");
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const response = await workspaceService.createWorkspaceAgent(workspaceSlug, {
        agent_id: agentId,
        display_name: displayName,
        email: email || undefined,
        workspace_role: role,
        agent_type: agentType,
        runtime_provider: runtimeProvider,
        endpoint_url: endpointUrl,
        default_model: defaultModel,
        secret_reference: secretReference,
        capability_claims: commaSeparated(capabilities),
        boundaries: { denied_capabilities: commaSeparated(deniedCapabilities) },
        create_token: true,
      });
      await onAgentCreated();
      reset();
      if (response.token) setGeneratedToken(response.token);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Agent created",
        message: `${displayName} can now use Mesh.`,
      });
    } catch (error) {
      const message = (error as { error?: string })?.error || "Could not create the agent.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Agent creation failed", message });
    } finally {
      setSubmitting(false);
    }
  };

  const review = async (application: Application, action: "approve" | "reject") => {
    try {
      const response = await workspaceService.reviewAgentApplication(workspaceSlug, application.id, {
        action,
        role: application.requested_role,
      });
      await mutate(applicationsKey);
      if (action === "approve") {
        await onAgentCreated();
        if (response.account?.token) setGeneratedToken(response.account.token);
      }
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: action === "approve" ? "Agent approved" : "Application rejected",
        message: `${application.display_name}'s application was ${action === "approve" ? "approved" : "rejected"}.`,
      });
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Review failed",
        message: (error as { error?: string })?.error || "Could not review the application.",
      });
    }
  };

  if (generatedToken) {
    return (
      <ModalCore
        isOpen={isOpen}
        handleClose={() => setGeneratedToken(null)}
        position={EModalPosition.TOP}
        width={EModalWidth.XXL}
      >
        <GeneratedTokenDetails handleClose={() => setGeneratedToken(null)} tokenDetails={generatedToken} />
      </ModalCore>
    );
  }

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose} position={EModalPosition.TOP} width={EModalWidth.XXL}>
      <div className="max-h-[85vh] divide-y divide-subtle overflow-y-auto">
        <div className="p-5">
          <div className="flex items-start gap-3">
            <Bot className="mt-0.5 size-5 text-secondary" />
            <div>
              <h3 className="text-18 font-medium text-primary">Agent management</h3>
              <p className="mt-1 text-13 text-secondary">Create approved agents or review bootstrap applications.</p>
            </div>
          </div>
          <div className="mt-4 inline-flex rounded-md border border-subtle bg-surface-2 p-0.5">
            <button
              type="button"
              className={`rounded px-3 py-1.5 text-13 ${mode === "agents" ? "shadow-sm bg-surface-1 text-primary" : "text-secondary"}`}
              onClick={() => setMode("agents")}
            >
              Agents ({agents?.length ?? 0})
            </button>
            <button
              type="button"
              className={`rounded px-3 py-1.5 text-13 ${mode === "create" ? "shadow-sm bg-surface-1 text-primary" : "text-secondary"}`}
              onClick={() => setMode("create")}
            >
              Create Agent
            </button>
            <button
              type="button"
              className={`rounded px-3 py-1.5 text-13 ${mode === "applications" ? "shadow-sm bg-surface-1 text-primary" : "text-secondary"}`}
              onClick={() => setMode("applications")}
            >
              Applications ({applications?.length ?? 0})
            </button>
          </div>
        </div>

        {mode === "agents" ? (
          <div className="max-h-[560px] overflow-auto p-5">
            {agentsLoading ? (
              <div className="text-13 text-placeholder">Loading agents...</div>
            ) : selectedAgentId ? (
              <AgentEditor
                key={selectedAgentId}
                agent={agents?.find((agent) => agent.workspace_member_id === selectedAgentId)!}
                workspaceSlug={workspaceSlug}
                onBack={() => setSelectedAgentId(null)}
                onUpdated={async () => {
                  await mutate(agentsKey);
                  await onAgentCreated();
                }}
              />
            ) : agents?.length ? (
              <div className="divide-y divide-subtle border-y border-subtle">
                {agents.map((agent) => (
                  <button
                    key={agent.workspace_member_id}
                    type="button"
                    className="flex w-full items-center justify-between gap-4 py-3 text-left"
                    onClick={() => setSelectedAgentId(agent.workspace_member_id)}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-13 font-medium text-primary">
                        {agent.display_name}{" "}
                        <span className="font-normal text-placeholder">agent:{agent.agent_id}</span>
                      </div>
                      <div className="truncate text-11 text-secondary">
                        {agent.agent_profile?.agent_type ?? "Agent"} ·{" "}
                        {agent.agent_profile?.runtime_provider ?? "unconfigured"} ·{" "}
                        {agent.default_execution?.model ?? "no model"}
                      </div>
                      <div className="mt-1 text-11 text-tertiary">
                        Agent Card: {agent.agent_profile?.agent_card?.available ? "available" : "unavailable"}
                      </div>
                    </div>
                    <Settings2 className="size-4 flex-shrink-0 text-secondary" />
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-13 text-placeholder">No Agent accounts in this workspace.</div>
            )}
          </div>
        ) : mode === "create" ? (
          <form onSubmit={handleCreate} className="space-y-4 p-5">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Agent ID" value={agentId} onChange={setAgentId} placeholder="iris" required />
              <Field label="Display name" value={displayName} onChange={setDisplayName} placeholder="Iris" required />
            </div>
            <Field
              label="Email (optional)"
              value={email}
              onChange={setEmail}
              placeholder={`agent-${agentId || "id"}@agentpm.local`}
            />
            <div className="grid grid-cols-2 gap-4">
              <label className="block space-y-1.5 text-13 text-secondary">
                <span>Agent type</span>
                <select
                  className="focus:border-accent h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-primary outline-none"
                  value={agentType}
                  onChange={(event) => setAgentType(event.target.value)}
                >
                  <option value="autonomous">Autonomous</option>
                  <option value="assistant">Assistant</option>
                  <option value="remote">Remote</option>
                  <option value="service">Service</option>
                </select>
              </label>
              <Field
                label="Runtime provider"
                value={runtimeProvider}
                onChange={setRuntimeProvider}
                placeholder="openclaw"
                required
              />
            </div>
            <Field
              label="Agent endpoint (optional)"
              value={endpointUrl}
              onChange={setEndpointUrl}
              placeholder="https://agent.tailnet.ts.net/a2a"
            />
            <div className="grid grid-cols-2 gap-4">
              <Field
                label="Default model (optional)"
                value={defaultModel}
                onChange={setDefaultModel}
                placeholder="gpt-5"
              />
              <Field
                label="Secret reference (optional)"
                value={secretReference}
                onChange={setSecretReference}
                placeholder="env:OPENCLAW_TOKEN"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field
                label="Capabilities"
                value={capabilities}
                onChange={setCapabilities}
                placeholder="code.write, test.run"
              />
              <Field
                label="Denied capabilities"
                value={deniedCapabilities}
                onChange={setDeniedCapabilities}
                placeholder="deploy.production"
              />
            </div>
            <label className="block space-y-1.5 text-13 text-secondary">
              <span>Workspace role</span>
              <select
                className="focus:border-accent h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-primary outline-none"
                value={role}
                onChange={(event) => setRole(event.target.value)}
              >
                <option value="member">Member</option>
                <option value="guest">Guest</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={submitting || !agentId || !displayName}>
                {submitting ? "Creating..." : "Create Agent"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="max-h-[420px] overflow-auto p-5">
            {isLoading ? (
              <div className="text-13 text-placeholder">Loading applications...</div>
            ) : applications?.length ? (
              <div className="divide-y divide-subtle border-y border-subtle">
                {applications.map((application) => (
                  <div key={application.id} className="flex items-center justify-between gap-4 py-3">
                    <div className="min-w-0">
                      <div className="truncate text-13 font-medium text-primary">
                        {application.display_name}{" "}
                        <span className="font-normal text-placeholder">agent:{application.agent_id}</span>
                      </div>
                      <div className="truncate text-11 text-secondary">
                        {application.agent_type} · {application.runtime_provider} · {application.requested_role}
                      </div>
                      {application.capability_claims.length > 0 && (
                        <div className="mt-1 line-clamp-1 text-11 text-secondary">
                          Capabilities: {application.capability_claims.join(", ")}
                        </div>
                      )}
                      {application.reason && (
                        <div className="mt-1 line-clamp-2 text-12 text-secondary">{application.reason}</div>
                      )}
                    </div>
                    <div className="flex flex-shrink-0 gap-1">
                      <button
                        type="button"
                        className="grid size-8 place-items-center rounded text-success-primary hover:bg-success-primary/10"
                        aria-label={`Approve ${application.display_name}`}
                        onClick={() => void review(application, "approve")}
                      >
                        <Check className="size-4" />
                      </button>
                      <button
                        type="button"
                        className="grid size-8 place-items-center rounded text-danger-primary hover:bg-danger-primary/10"
                        aria-label={`Reject ${application.display_name}`}
                        onClick={() => void review(application, "reject")}
                      >
                        <X className="size-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-13 text-placeholder">No pending Agent applications.</div>
            )}
          </div>
        )}
      </div>
    </ModalCore>
  );
}

function AgentEditor({
  agent,
  onBack,
  onUpdated,
  workspaceSlug,
}: {
  agent: WorkspaceAgent;
  onBack: () => void;
  onUpdated: () => Promise<unknown>;
  workspaceSlug: string;
}) {
  const profile = agent.agent_profile;
  const execution = agent.default_execution;
  const [endpointUrl, setEndpointUrl] = useState(profile?.endpoint_url ?? "");
  const [agentType, setAgentType] = useState(profile?.agent_type ?? "autonomous");
  const [runtimeProvider, setRuntimeProvider] = useState(profile?.runtime_provider ?? "custom");
  const [agentStatus, setAgentStatus] = useState(profile?.status ?? "pending");
  const [trustLevel, setTrustLevel] = useState(profile?.trust_level ?? "unverified");
  const [role, setRole] = useState(String(agent.role));
  const [isActive, setIsActive] = useState(agent.is_active);
  const [capabilities, setCapabilities] = useState((profile?.capability_claims ?? []).join(", "));
  const [deniedCapabilities, setDeniedCapabilities] = useState(
    (profile?.boundaries?.denied_capabilities ?? []).join(", ")
  );
  const [provider, setProvider] = useState(execution?.provider ?? profile?.runtime_provider ?? "custom");
  const [model, setModel] = useState(execution?.model ?? "");
  const [configurationVersion, setConfigurationVersion] = useState(String(execution?.configuration_version ?? 1));
  const [secretReference, setSecretReference] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await workspaceService.updateWorkspaceAgent(workspaceSlug, agent.workspace_member_id, {
        role: Number(role),
        is_active: isActive,
        agent_type: agentType,
        runtime_provider: runtimeProvider,
        endpoint_url: endpointUrl,
        status: agentStatus,
        trust_level: trustLevel,
        capability_claims: commaSeparated(capabilities),
        boundaries: { denied_capabilities: commaSeparated(deniedCapabilities) },
        default_execution: model
          ? {
              provider,
              model,
              configuration_version: Number(configurationVersion),
              ...(secretReference ? { secret_reference: secretReference } : {}),
              settings: execution?.settings ?? {},
              is_active: true,
            }
          : undefined,
      });
      await onUpdated();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Agent updated",
        message: `${agent.display_name}'s runtime profile is current.`,
      });
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Agent update failed",
        message: (error as { error?: string })?.error || "Could not update the Agent.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const syncCard = async () => {
    setSubmitting(true);
    try {
      await workspaceService.syncWorkspaceAgentCard(workspaceSlug, agent.workspace_member_id);
      await onUpdated();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Agent Card synced",
        message: `${agent.display_name} is available for Mesh runs.`,
      });
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Agent Card unavailable",
        message: (error as { error?: string })?.error || "Could not reach the Agent Card.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-13 font-medium text-primary">{agent.display_name}</div>
          <div className="text-11 text-secondary">agent:{agent.agent_id}</div>
        </div>
        <Button variant="secondary" type="button" onClick={onBack}>
          Back
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <label className="block space-y-1.5 text-13 text-secondary">
          <span>Agent type</span>
          <select
            className="h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-primary"
            value={agentType}
            onChange={(event) => setAgentType(event.target.value)}
          >
            <option value="autonomous">Autonomous</option>
            <option value="assistant">Assistant</option>
            <option value="remote">Remote</option>
            <option value="service">Service</option>
          </select>
        </label>
        <Field
          label="Runtime provider"
          value={runtimeProvider}
          onChange={setRuntimeProvider}
          placeholder="openclaw"
          required
        />
      </div>
      <Field
        label="A2A endpoint"
        value={endpointUrl}
        onChange={setEndpointUrl}
        placeholder="http://100.x.y.z:18890/agents/iris/a2a"
      />
      <div className="grid grid-cols-3 gap-4">
        <SelectField
          label="Status"
          value={agentStatus}
          onChange={setAgentStatus}
          options={["pending", "active", "suspended", "retired"]}
        />
        <SelectField
          label="Trust"
          value={trustLevel}
          onChange={setTrustLevel}
          options={["unverified", "verified", "trusted"]}
        />
        <label className="block space-y-1.5 text-13 text-secondary">
          <span>Workspace role</span>
          <select
            className="h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-primary"
            value={role}
            onChange={(event) => setRole(event.target.value)}
          >
            <option value="20">Admin</option>
            <option value="15">Member</option>
            <option value="5">Guest</option>
          </select>
        </label>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Field
          label="Capabilities"
          value={capabilities}
          onChange={setCapabilities}
          placeholder="code.write, test.run"
        />
        <Field
          label="Denied capabilities"
          value={deniedCapabilities}
          onChange={setDeniedCapabilities}
          placeholder="deploy.production"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Execution provider" value={provider} onChange={setProvider} placeholder="openclaw" />
        <Field label="Model" value={model} onChange={setModel} placeholder="runtime-reported" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Field
          label="Configuration version"
          value={configurationVersion}
          onChange={setConfigurationVersion}
          placeholder="1"
        />
        <Field
          label="New secret reference"
          value={secretReference}
          onChange={setSecretReference}
          placeholder={
            execution?.has_secret_reference ? "Configured; enter a value to rotate" : "env:MESH_AGENT_GATEWAY_TOKEN"
          }
        />
      </div>
      <label className="flex items-center gap-2 text-13 text-secondary">
        <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
        Active workspace and project memberships
      </label>
      {profile?.agent_card?.sync_error && (
        <div className="rounded border border-danger-subtle bg-danger-subtle/20 p-2 text-11 text-danger-primary">
          {profile.agent_card.sync_error}
        </div>
      )}
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" type="button" onClick={() => void syncCard()} disabled={submitting || !endpointUrl}>
          <RefreshCw className="mr-1.5 size-4" /> Sync Agent Card
        </Button>
        <Button variant="primary" type="submit" disabled={submitting}>
          {submitting ? "Saving..." : "Save Agent"}
        </Button>
      </div>
    </form>
  );
}

function SelectField({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: string[];
  value: string;
}) {
  return (
    <label className="block space-y-1.5 text-13 text-secondary">
      <span>{label}</span>
      <select
        className="h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-primary"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option[0].toUpperCase() + option.slice(1)}
          </option>
        ))}
      </select>
    </label>
  );
}

function commaSeparated(value: string): string[] {
  return [
    ...new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
    ),
  ];
}

function Field({
  label,
  onChange,
  placeholder,
  required = false,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  placeholder: string;
  required?: boolean;
  value: string;
}) {
  return (
    <label className="block space-y-1.5 text-13 text-secondary">
      <span>{label}</span>
      <input
        className="focus:border-accent h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-primary outline-none placeholder:text-placeholder"
        value={value}
        placeholder={placeholder}
        required={required}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
