/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import { Bot, ChevronDownIcon } from "lucide-react";
// plane imports
import { EUserPermissions, ROLE } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Avatar, CustomSearchSelect, CustomSelect, EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { getFileURL } from "@plane/utils";
// services
import projectMemberService, { type TProjectAgentMember } from "@/services/project/project-member.service";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  projectId: string;
  workspaceSlug: string;
};

const projectAgentsKey = (workspaceSlug: string, projectId: string) =>
  `PROJECT_AGENT_MEMBERS_${workspaceSlug}_${projectId}`;

export function AddProjectAgentModal(props: Props) {
  const { isOpen, onClose, onSuccess, projectId, workspaceSlug } = props;
  const [selectedUserId, setSelectedUserId] = useState("");
  const [role, setRole] = useState<EUserPermissions>(EUserPermissions.MEMBER);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const key = projectAgentsKey(workspaceSlug, projectId);
  const { data: agents, isLoading } = useSWR(isOpen ? key : null, () =>
    projectMemberService.fetchProjectAgentMembers(workspaceSlug, projectId)
  );

  const availableAgents = useMemo(() => (agents ?? []).filter((agent) => !agent.project_role), [agents]);
  const selectedAgent = availableAgents.find((agent) => agent.user_id === selectedUserId);

  const options = availableAgents.map((agent) => ({
    value: agent.user_id,
    query: `${agent.display_name} ${agent.agent_id ?? ""} ${agent.email}`,
    content: <AgentOption agent={agent} />,
  }));

  const handleClose = () => {
    onClose();
    setTimeout(() => {
      setSelectedUserId("");
      setRole(EUserPermissions.MEMBER);
    }, 300);
  };

  const handleSubmit = async () => {
    if (!selectedUserId || isSubmitting) return;
    setIsSubmitting(true);
    await projectMemberService
      .addAgentMemberToProject(workspaceSlug, projectId, { user_id: selectedUserId, role })
      .then(() => {
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Agent added",
          message: "The agent can now participate in this project.",
        });
        void mutate(key);
        onSuccess?.();
        handleClose();
      })
      .catch((err: { error?: string; message?: string }) => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Could not add agent",
          message: err?.error || err?.message || "The agent could not be added to this project.",
        });
      })
      .finally(() => setIsSubmitting(false));
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.CENTER} width={EModalWidth.XXL}>
      <div className="space-y-5 p-5">
        <div className="space-y-1">
          <h3 className="text-16 leading-6 font-medium text-primary">Add Agent</h3>
          <p className="text-13 text-secondary">Add an approved workspace agent to this project.</p>
        </div>

        <div className="space-y-4">
          <div className="space-y-1">
            <div className="text-13 font-medium text-primary">Agent</div>
            <CustomSearchSelect
              value={selectedUserId}
              customButton={
                <button className="shadow-sm flex w-full items-center justify-between gap-1 rounded-md border border-subtle px-3 py-2 text-left text-13 text-secondary duration-300 hover:bg-layer-1 hover:text-primary focus:outline-none">
                  {selectedAgent ? <AgentOption agent={selectedAgent} /> : <span>Select agent</span>}
                  <ChevronDownIcon className="size-3" aria-hidden="true" />
                </button>
              }
              onChange={(value: string) => setSelectedUserId(value)}
              options={options}
              optionsClassName="w-64"
            />
            {!isLoading && availableAgents.length === 0 && (
              <p className="text-12 text-placeholder">
                No approved workspace agents are available for this project.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <div className="text-13 font-medium text-primary">Project role</div>
            <CustomSelect
              value={role}
              onChange={(value: EUserPermissions) => setRole(Number(value) as EUserPermissions)}
              customButton={
                <div className="shadow-sm flex w-36 items-center justify-between gap-1 rounded-md border border-subtle px-3 py-2.5 text-left text-13 text-secondary duration-300 hover:bg-layer-1 hover:text-primary focus:outline-none">
                  <span>{ROLE[role]}</span>
                  <ChevronDownIcon className="size-3" aria-hidden="true" />
                </div>
              }
              input
            >
              {[EUserPermissions.MEMBER, EUserPermissions.GUEST, EUserPermissions.ADMIN].map((option) => (
                <CustomSelect.Option key={option} value={option}>
                  {ROLE[option]}
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="lg"
            loading={isSubmitting}
            disabled={!selectedUserId || availableAgents.length === 0}
            onClick={() => void handleSubmit()}
          >
            Add Agent
          </Button>
        </div>
      </div>
    </ModalCore>
  );
}

function AgentOption({ agent }: { agent: TProjectAgentMember }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <div className="shrink-0 pt-0.5">
        {agent.avatar_url ? (
          <Avatar name={agent.display_name} src={getFileURL(agent.avatar_url)} />
        ) : (
          <div className="grid size-6 place-items-center rounded-full bg-layer-3 text-secondary">
            <Bot className="size-3.5" />
          </div>
        )}
      </div>
      <div className="min-w-0">
        <div className="truncate text-13 text-primary">{agent.display_name}</div>
        <div className="truncate text-11 text-placeholder">{agent.agent_id ? `agent:${agent.agent_id}` : agent.email}</div>
      </div>
    </div>
  );
}
