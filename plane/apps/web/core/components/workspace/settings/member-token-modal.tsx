/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR, { mutate } from "swr";
// plane imports
import { Button } from "@plane/propel/button";
import { Trash2 } from "lucide-react";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IApiToken } from "@plane/types";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { renderFormattedDate, renderFormattedTime } from "@plane/utils";
// components
import { CreateApiTokenForm } from "@/components/api-token/modal/form";
import { GeneratedTokenDetails } from "@/components/api-token/modal/generated-token-details";
import type { RowData } from "@/components/workspace/settings/member-columns";
import { WorkspaceService } from "@/services/workspace.service";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  member: RowData;
  workspaceSlug: string;
};

const workspaceService = new WorkspaceService();

const memberTokenKey = (workspaceSlug: string, memberId: string) =>
  `WORKSPACE_MEMBER_API_TOKENS_${workspaceSlug}_${memberId}`;

export function WorkspaceMemberTokenModal(props: Props) {
  const { isOpen, member, onClose, workspaceSlug } = props;
  const [neverExpires, setNeverExpires] = useState<boolean>(false);
  const [generatedToken, setGeneratedToken] = useState<IApiToken | null>(null);
  const key = memberTokenKey(workspaceSlug, member.member.id);

  const { data: tokens, isLoading } = useSWR(isOpen ? key : null, () =>
    workspaceService.listWorkspaceMemberApiTokens(workspaceSlug, member.member.id)
  );

  const handleClose = () => {
    onClose();
    setTimeout(() => {
      setGeneratedToken(null);
      setNeverExpires(false);
    }, 350);
  };

  const handleCreateToken = async (data: Partial<IApiToken>) => {
    await workspaceService
      .createWorkspaceMemberApiToken(workspaceSlug, member.member.id, {
        ...data,
        label: data.label || `AgentPM ${member.member.display_name} MCP`,
      })
      .then((res: IApiToken) => {
        setGeneratedToken(res);
        void mutate(key);
      })
      .catch((err: { error?: string; message?: string }) => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error!",
          message: err?.error || err?.message || "Could not create agent token.",
        });
        throw err;
      });
  };

  const handleDeleteToken = async (tokenId: string) => {
    await workspaceService
      .deleteWorkspaceMemberApiToken(workspaceSlug, member.member.id, tokenId)
      .then(() => {
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Token deleted",
          message: "The agent token has been revoked.",
        });
        void mutate(key);
      })
      .catch((err: { error?: string; message?: string }) => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error!",
          message: err?.error || err?.message || "Could not delete agent token.",
        });
      });
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.TOP} width={EModalWidth.XXL}>
      {generatedToken ? (
        <GeneratedTokenDetails handleClose={() => setGeneratedToken(null)} tokenDetails={generatedToken} />
      ) : (
        <div className="divide-y divide-subtle">
          <div className="space-y-1 p-5">
            <h3 className="text-18 font-medium text-primary">Agent tokens</h3>
            <p className="text-13 text-secondary">
              Manage Plane API tokens for {member.member.display_name || member.member.email}.
            </p>
          </div>
          <div className="max-h-56 overflow-auto p-5">
            {isLoading ? (
              <div className="text-13 text-placeholder">Loading tokens...</div>
            ) : tokens && tokens.length > 0 ? (
              <div className="space-y-2">
                {tokens.map((token) => (
                  <div
                    key={token.id}
                    className="flex items-center justify-between gap-3 rounded-md border border-subtle px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-13 font-medium text-primary">{token.label}</div>
                      <div className="text-11 text-placeholder">
                        {token.expired_at
                          ? `Expires ${renderFormattedDate(token.expired_at)} at ${renderFormattedTime(token.expired_at)}`
                          : "Never expires"}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="grid size-7 flex-shrink-0 place-items-center rounded text-danger-primary hover:bg-danger-primary/10"
                      onClick={() => void handleDeleteToken(token.id)}
                      aria-label={`Delete ${token.label}`}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-13 text-placeholder">No agent tokens yet.</div>
            )}
          </div>
          <CreateApiTokenForm
            handleClose={handleClose}
            neverExpires={neverExpires}
            toggleNeverExpires={() => setNeverExpires((prev) => !prev)}
            onSubmit={handleCreateToken}
          />
          <div className="flex justify-end p-5 pt-0">
            <Button variant="secondary" onClick={handleClose}>
              Close
            </Button>
          </div>
        </div>
      )}
    </ModalCore>
  );
}
