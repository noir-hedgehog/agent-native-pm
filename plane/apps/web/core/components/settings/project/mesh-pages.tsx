/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Check, Save, Search, Send, X } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Input, TextArea } from "@plane/ui";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";

type ProjectParams = { projectId: string; workspaceSlug: string };
type Role = { id: string; key: string; name: string; capabilities: string[] };
type Policy = {
  id: string;
  version: number;
  source_yaml: string;
  change_note: string;
  published_at: string;
};
type SkillVersion = { id: string; version: string; status: string; checksum: string };
type Skill = {
  id: string;
  name: string;
  slug: string;
  description: string;
  published_version: string | null;
  versions?: SkillVersion[];
};
type LoopDefinition = {
  id: string;
  name: string;
  slug: string;
  version: number;
  status: string;
  source_yaml: string;
  graph: { nodes?: Array<Record<string, unknown>>; edges?: Array<Record<string, unknown>> };
};
type LoopRunSummary = {
  id: string;
  definition_id: string;
  status: string;
  work_item_name: string;
};
type Approval = {
  id: string;
  status: string;
  work_item_name: string;
  created_at: string;
  decision_note: string;
};

const requestJson = async <T,>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, { credentials: "include", ...init });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Request failed");
  return payload as T;
};

const showError = (error: unknown) =>
  setToast({
    type: TOAST_TYPE.ERROR,
    title: "Mesh request failed",
    message: error instanceof Error ? error.message : "Please try again.",
  });

export function MeshPolicySettings({ params }: { params: ProjectParams }) {
  const base = `/api/workspaces/${params.workspaceSlug}/projects/${params.projectId}/mesh`;
  const [roles, setRoles] = useState<Role[]>([]);
  const [history, setHistory] = useState<Policy[]>([]);
  const [source, setSource] = useState("");
  const [changeNote, setChangeNote] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [roleResult, policyResult] = await Promise.all([
        requestJson<{ roles: Role[] }>(`${base}/roles/`),
        requestJson<{ policies: Policy[] }>(`${base}/policy/?history=true`),
      ]);
      setRoles(roleResult.roles);
      setHistory(policyResult.policies);
      setSource((current) => {
        if (current) return current;
        const latest = policyResult.policies[0];
        return latest?.source_yaml || defaultPolicyYaml(roleResult.roles);
      });
    } catch (error) {
      showError(error);
    }
  }, [base]);

  useEffect(() => void load(), [load]);

  const publish = async () => {
    setSaving(true);
    try {
      await requestJson(`${base}/policy/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_yaml: source, change_note: changeNote }),
      });
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Policy published", message: "" });
      setChangeNote("");
      await load();
    } catch (error) {
      showError(error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsContentWrapper>
      <SettingsHeading title="Roles & Policy" description={`${roles.length} functional roles`} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div>
          <TextArea
            value={source}
            onChange={(event) => setSource(event.target.value)}
            rows={24}
            className="font-mono"
          />
          <div className="mt-3 flex items-center gap-2">
            <Input
              value={changeNote}
              onChange={(event) => setChangeNote(event.target.value)}
              placeholder="Change note"
            />
            <Button onClick={() => void publish()} loading={saving} prependIcon={<Save className="size-3.5" />}>
              Publish
            </Button>
          </div>
        </div>
        <div className="divide-y divide-subtle border-y border-subtle">
          {history.map((policy) => (
            <button
              key={policy.id}
              type="button"
              onClick={() => setSource(policy.source_yaml)}
              className="flex w-full items-center justify-between py-3 text-left text-13"
            >
              <span className="text-primary">v{policy.version}</span>
              <span className="max-w-40 truncate text-secondary">{policy.change_note || "Published"}</span>
            </button>
          ))}
        </div>
      </div>
    </SettingsContentWrapper>
  );
}

export function MeshSkillsSettings({ params }: { params: ProjectParams }) {
  const base = `/api/workspaces/${params.workspaceSlug}/projects/${params.projectId}/mesh`;
  const [skills, setSkills] = useState<Skill[]>([]);
  const [source, setSource] = useState(DEFAULT_SKILL);
  const load = useCallback(async () => {
    try {
      setSkills((await requestJson<{ skills: Skill[] }>(`${base}/skills/`)).skills);
    } catch (error) {
      showError(error);
    }
  }, [base]);
  useEffect(() => void load(), [load]);
  const submit = async () => {
    try {
      await requestJson(`${base}/skills/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_text: source }),
      });
      await load();
    } catch (error) {
      showError(error);
    }
  };
  const publish = async (versionId: string) => {
    try {
      await requestJson(`${base}/skills/versions/${versionId}/publish/`, { method: "POST" });
      await load();
    } catch (error) {
      showError(error);
    }
  };
  return (
    <SettingsContentWrapper>
      <SettingsHeading title="Skills" description={`${skills.length} project skills`} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <TextArea
            value={source}
            onChange={(event) => setSource(event.target.value)}
            rows={22}
            className="font-mono"
          />
          <Button className="mt-3" onClick={() => void submit()} prependIcon={<Send className="size-3.5" />}>
            Submit draft
          </Button>
        </div>
        <div className="divide-y divide-subtle border-y border-subtle">
          {skills.map((skill) => (
            <div key={skill.id} className="py-3">
              <div className="flex items-center justify-between gap-2">
                <div className="truncate text-13 font-medium text-primary">{skill.name}</div>
                <span className="text-11 text-secondary">{skill.published_version || "Draft"}</span>
              </div>
              <div className="mt-1 text-12 text-secondary">{skill.description}</div>
              {skill.versions
                ?.filter((version) => version.status === "pending")
                .map((version) => (
                  <Button
                    key={version.id}
                    variant="secondary"
                    size="sm"
                    className="mt-2"
                    onClick={() => void publish(version.id)}
                    prependIcon={<Check className="size-3" />}
                  >
                    Publish {version.version}
                  </Button>
                ))}
            </div>
          ))}
        </div>
      </div>
    </SettingsContentWrapper>
  );
}

export function MeshKnowledgeSettings({ params }: { params: ProjectParams }) {
  const base = `/api/workspaces/${params.workspaceSlug}/projects/${params.projectId}/mesh`;
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<
    Array<{
      id: string;
      heading: string;
      content: string;
      citation: { page_id: string; page_name: string; heading: string };
    }>
  >([]);
  const search = async () => {
    try {
      setResults(
        (
          await requestJson<{ results: typeof results }>(`${base}/knowledge/search/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
          })
        ).results
      );
    } catch (error) {
      showError(error);
    }
  };
  return (
    <SettingsContentWrapper>
      <SettingsHeading title="Knowledge" description="Project Page index" />
      <div className="flex max-w-2xl items-center gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search knowledge"
          onKeyDown={(event) => event.key === "Enter" && void search()}
        />
        <Button onClick={() => void search()} prependIcon={<Search className="size-3.5" />}>
          Search
        </Button>
      </div>
      <div className="mt-6 max-w-4xl divide-y divide-subtle border-y border-subtle">
        {results.map((result) => (
          <div key={result.id} className="py-4">
            <div className="text-13 font-medium text-primary">
              {result.citation.page_name}
              {result.heading ? ` / ${result.heading}` : ""}
            </div>
            <div className="mt-1 line-clamp-3 text-13 whitespace-pre-wrap text-secondary">{result.content}</div>
            <div className="font-mono mt-2 text-11 text-tertiary">page:{result.citation.page_id}</div>
          </div>
        ))}
      </div>
    </SettingsContentWrapper>
  );
}

export function MeshLoopsSettings({ params }: { params: ProjectParams }) {
  const base = `/api/workspaces/${params.workspaceSlug}/projects/${params.projectId}/mesh`;
  const [loops, setLoops] = useState<LoopDefinition[]>([]);
  const [source, setSource] = useState(DEFAULT_LOOP);
  const [selected, setSelected] = useState<LoopDefinition | null>(null);
  const [runs, setRuns] = useState<LoopRunSummary[]>([]);
  const [mode, setMode] = useState<"canvas" | "yaml">("canvas");
  const load = useCallback(async () => {
    try {
      const [loopResult, runResult] = await Promise.all([
        requestJson<{ loops: LoopDefinition[] }>(`${base}/loops/`),
        requestJson<{ runs: LoopRunSummary[] }>(`${base}/runs/`),
      ]);
      const rows = loopResult.loops;
      setLoops(rows);
      setRuns(runResult.runs);
      setSelected((current) => rows.find((loop) => loop.id === current?.id) || rows[0] || null);
    } catch (error) {
      showError(error);
    }
  }, [base]);
  useEffect(() => void load(), [load]);
  const saveDraft = async () => {
    try {
      const { loop } = await requestJson<{ loop: LoopDefinition }>(`${base}/loops/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_yaml: source }),
      });
      setSelected(loop);
      await load();
    } catch (error) {
      showError(error);
    }
  };
  const publish = async () => {
    if (!selected) return;
    try {
      await requestJson(`${base}/loops/${selected.id}/publish/`, { method: "POST" });
      await load();
    } catch (error) {
      showError(error);
    }
  };
  const graph = useMemo(() => graphElements(selected), [selected]);
  return (
    <SettingsContentWrapper>
      <SettingsHeading
        title="Loops"
        description={`${loops.length} definitions / ${runs.length} runs / ${runs.filter((run) => ["queued", "running", "waiting_for_assignee", "awaiting_approval"].includes(run.status)).length} active`}
      />
      <div className="mb-3 flex items-center justify-between gap-3 border-b border-subtle">
        <div className="flex items-center">
          {(["canvas", "yaml"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value)}
              className={`h-9 border-b-2 px-3 text-12 capitalize ${mode === value ? "border-accent-strong text-primary" : "border-transparent text-secondary"}`}
            >
              {value}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void saveDraft()}
            prependIcon={<Save className="size-3" />}
          >
            Save draft
          </Button>
          <Button
            size="sm"
            disabled={!selected || selected.status === "published"}
            onClick={() => void publish()}
            prependIcon={<Check className="size-3" />}
          >
            Publish
          </Button>
        </div>
      </div>
      <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        <div className="divide-y divide-subtle border-y border-subtle">
          {loops.map((loop) => (
            <button
              key={loop.id}
              type="button"
              onClick={() => {
                setSelected(loop);
                setSource(loop.source_yaml);
              }}
              className="w-full py-3 text-left"
            >
              <div className="truncate text-13 text-primary">{loop.name}</div>
              <div className="text-11 text-secondary">
                v{loop.version} / {loop.status} / {runs.filter((run) => run.definition_id === loop.id).length} runs
              </div>
            </button>
          ))}
        </div>
        {mode === "yaml" ? (
          <TextArea
            value={source}
            onChange={(event) => setSource(event.target.value)}
            rows={26}
            className="font-mono"
          />
        ) : (
          <div className="h-[620px] min-h-[420px] border border-subtle bg-surface-1">
            <ReactFlow
              nodes={graph.nodes}
              edges={graph.edges}
              fitView
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        )}
      </div>
    </SettingsContentWrapper>
  );
}

export function MeshApprovalsSettings({ params }: { params: ProjectParams }) {
  const base = `/api/workspaces/${params.workspaceSlug}/projects/${params.projectId}/mesh`;
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const load = useCallback(async () => {
    try {
      setApprovals((await requestJson<{ approvals: Approval[] }>(`${base}/approvals/`)).approvals);
    } catch (error) {
      showError(error);
    }
  }, [base]);
  useEffect(() => void load(), [load]);
  const decide = async (id: string, decision: "approve" | "reject") => {
    try {
      await requestJson(`${base}/approvals/${id}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      await load();
    } catch (error) {
      showError(error);
    }
  };
  return (
    <SettingsContentWrapper>
      <SettingsHeading
        title="Approvals"
        description={`${approvals.filter((item) => item.status === "pending").length} pending`}
      />
      <div className="max-w-4xl divide-y divide-subtle border-y border-subtle">
        {approvals.map((approval) => (
          <div key={approval.id} className="flex items-center justify-between gap-4 py-3">
            <div>
              <div className="text-13 text-primary">{approval.work_item_name}</div>
              <div className="text-11 text-secondary">{approval.status}</div>
            </div>
            {approval.status === "pending" && (
              <div className="flex items-center gap-1">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void decide(approval.id, "reject")}
                  prependIcon={<X className="size-3" />}
                >
                  Reject
                </Button>
                <Button
                  size="sm"
                  onClick={() => void decide(approval.id, "approve")}
                  prependIcon={<Check className="size-3" />}
                >
                  Approve
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </SettingsContentWrapper>
  );
}

function graphElements(loop: LoopDefinition | null): { nodes: Node[]; edges: Edge[] } {
  if (!loop) return { nodes: [], edges: [] };
  const nodes = (loop.graph.nodes || []).map((node, index) => ({
    id: String(node.id),
    position: { x: (index % 3) * 260, y: Math.floor(index / 3) * 150 },
    data: { label: `${String(node.type).toUpperCase()}\n${String(node.objective || node.id)}` },
    style: {
      borderRadius: 6,
      border: "1px solid var(--border-subtle)",
      width: 210,
      fontSize: 12,
      whiteSpace: "pre-line" as const,
    },
  }));
  const edges = (loop.graph.edges || []).map((edge, index) => ({
    id: `edge-${index}`,
    source: String(edge.from),
    target: String(edge.to),
  }));
  return { nodes, edges };
}

function defaultPolicyYaml(roles: Role[]) {
  const roleLines = roles
    .map((role) => `  ${role.key}:\n    capabilities: [${role.capabilities.join(", ")}]`)
    .join("\n");
  return `schema_version: 1\nroles:\n${roleLines}\nallowed_handoffs:\n${roles.map((role) => `  ${role.key}: []`).join("\n")}\ndelegation:\n  max_depth: 1\nbudgets: {}\napprovals: {}\n`;
}

const DEFAULT_SKILL = `---\nname: project-sop\ndescription: Project operating procedure\nversion: 0.1.0\n---\n# Procedure\n\nAdd the project SOP here.\n`;
const DEFAULT_LOOP = `schema_version: 1\nname: Bug fix\nlimits:\n  max_transitions: 12\nnodes:\n  - id: assigned\n    type: trigger\n  - id: repair\n    type: stage\n    objective: Reproduce and repair the defect\n    roles: [developer]\n    required_capabilities: [code.write]\n    evidence: [summary, tests]\n  - id: handoff\n    type: handoff\n  - id: verify\n    type: stage\n    objective: Verify the fix\n    roles: [tester]\n    evidence: [test_result]\n  - id: done\n    type: complete\nedges:\n  - from: assigned\n    to: repair\n  - from: repair\n    to: handoff\n  - from: handoff\n    to: verify\n  - from: verify\n    to: done\n`;
