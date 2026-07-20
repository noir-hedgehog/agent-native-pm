/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// types
import { API_BASE_URL } from "@plane/constants";
import type { IProjectBulkAddFormData, TProjectMembership } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export type TProjectAgentMember = {
  user_id: string;
  agent_id: string | null;
  display_name: string;
  email: string;
  avatar_url: string;
  workspace_role: number;
  project_member_id: string | null;
  project_role: number | null;
};

export type TMeshFunctionalRole = {
  id: string;
  key: string;
  name: string;
  description: string;
  capabilities: string[];
};

export class ProjectMemberService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetchProjectMembers(
    workspaceSlug: string,
    projectId: string,
  ): Promise<TProjectMembership[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/members/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async bulkAddMembersToProject(
    workspaceSlug: string,
    projectId: string,
    data: IProjectBulkAddFormData,
  ): Promise<TProjectMembership[]> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/members/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchProjectAgentMembers(
    workspaceSlug: string,
    projectId: string,
  ): Promise<TProjectAgentMember[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/agent-members/`)
      .then((response) => response?.data?.agents ?? [])
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async addAgentMemberToProject(
    workspaceSlug: string,
    projectId: string,
    data: { user_id: string; role: number },
  ): Promise<TProjectMembership[]> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/agent-members/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async fetchMeshFunctionalRoles(
    workspaceSlug: string,
    projectId: string,
  ): Promise<TMeshFunctionalRole[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/mesh/roles/`)
      .then((response) => response?.data?.roles ?? [])
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateMeshMemberRoles(
    workspaceSlug: string,
    projectId: string,
    projectMemberId: string,
    roleIds: string[],
  ): Promise<{ roles: TMeshFunctionalRole[] }> {
    return this.put(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/mesh/members/${projectMemberId}/roles/`,
      { role_ids: roleIds },
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async projectMemberMe(workspaceSlug: string, projectId: string): Promise<TProjectMembership> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/project-members/me/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async getProjectMember(
    workspaceSlug: string,
    projectId: string,
    memberId: string,
  ): Promise<TProjectMembership> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/members/${memberId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateProjectMember(
    workspaceSlug: string,
    projectId: string,
    memberId: string,
    data: Partial<TProjectMembership>,
  ): Promise<TProjectMembership> {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/members/${memberId}/`,
      data,
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteProjectMember(
    workspaceSlug: string,
    projectId: string,
    memberId: string,
  ): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/members/${memberId}/`,
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

const projectMemberService = new ProjectMemberService();

export default projectMemberService;
