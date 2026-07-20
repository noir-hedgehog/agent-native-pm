# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F
from rest_framework import status
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.app.views.project.mesh import (
    _knowledge_chunk_dict,
    _loop_definition_dict,
    _loop_run_dict,
    _policy_dict,
    _role_dict,
    _seed_default_roles,
    _skill_dict,
)
from plane.db.models import (
    AgentProfile,
    MeshFunctionalRole,
    MeshKnowledgeChunk,
    MeshLoopDefinition,
    MeshLoopRun,
    MeshProjectPolicy,
    MeshSkill,
    ProjectMember,
    Workspace,
    WorkspaceMember,
)
from plane.mesh.discovery import list_eligible_agents
from plane.utils.permissions import ProjectMemberPermission


class MeshWorkspaceEndpoint(BaseAPIView):
    def get(self, request, slug):
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if not workspace:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)
        membership = WorkspaceMember.objects.filter(
            workspace=workspace,
            member=request.user,
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        if not membership:
            return Response({"error": "Workspace membership is required"}, status=status.HTTP_403_FORBIDDEN)
        profile = AgentProfile.objects.filter(
            workspace=workspace,
            user=request.user,
            deleted_at__isnull=True,
        ).first()
        execution = profile.execution_profiles.filter(is_default=True, is_active=True).first() if profile else None
        return Response(
            {
                "name": "Mesh Agent-Native Collaboration API",
                "version": "v1",
                "workspace_id": str(workspace.id),
                "identity": {
                    "plane_user_id": str(request.user.id),
                    "display_name": request.user.display_name,
                    "account_type": "agent" if profile else "human",
                    "workspace_role": membership.role,
                    "agent_id": profile.agent_id if profile else None,
                    "agent_type": profile.agent_type if profile else None,
                    "runtime_provider": profile.runtime_provider if profile else None,
                    "capabilities": profile.capability_claims if profile else [],
                    "boundaries": profile.boundaries if profile else {},
                    "execution": {
                        "provider": execution.provider,
                        "model": execution.model,
                        "configuration_version": execution.configuration_version,
                    }
                    if execution
                    else None,
                },
                "resources": ["roles", "eligible-agents", "policy", "skills", "knowledge", "loops", "runs"],
            }
        )


class MeshProjectRolesAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectMemberPermission]

    def get(self, request, slug, project_id):
        member = _project_member(request.user.id, project_id)
        _seed_default_roles(str(project_id), str(member.workspace_id))
        roles = MeshFunctionalRole.objects.filter(project_id=project_id, deleted_at__isnull=True)
        return Response({"roles": [_role_dict(role) for role in roles]})


class MeshEligibleAgentsAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectMemberPermission]

    def get(self, request, slug, project_id):
        role = str(request.query_params.get("role") or "").strip()
        if not role:
            return Response({"error": "role is required"}, status=status.HTTP_400_BAD_REQUEST)
        capabilities = [
            value.strip() for value in str(request.query_params.get("capabilities") or "").split(",") if value.strip()
        ]
        agents = list_eligible_agents(
            project_id=str(project_id),
            role_keys=[role],
            required_capabilities=capabilities,
        )
        return Response({"agents": [agent.public_dict for agent in agents]})


class MeshProjectPolicyAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectMemberPermission]

    def get(self, request, slug, project_id):
        policies = MeshProjectPolicy.objects.filter(
            project_id=project_id,
            status=MeshProjectPolicy.Status.PUBLISHED,
            deleted_at__isnull=True,
        ).select_related("published_by")
        if request.query_params.get("history") == "true":
            return Response({"policies": [_policy_dict(policy) for policy in policies]})
        policy = policies.first()
        return Response({"policy": _policy_dict(policy) if policy else None})


class MeshSkillsAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectMemberPermission]

    def get(self, request, slug, project_id):
        skills = MeshSkill.objects.filter(project_id=project_id, deleted_at__isnull=True).prefetch_related("versions")
        return Response({"skills": [_skill_dict(skill) for skill in skills]})


class MeshKnowledgeSearchAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectMemberPermission]

    def post(self, request, slug, project_id):
        query_text = str(request.data.get("query") or "").strip()
        if not query_text:
            return Response({"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST)
        query = SearchQuery(query_text, search_type="websearch")
        chunks = (
            MeshKnowledgeChunk.objects.filter(project_id=project_id, deleted_at__isnull=True)
            .annotate(text_rank=SearchRank(F("content_search"), query))
            .filter(text_rank__gt=0)
            .select_related("document__page", "document__page_version")
            .order_by("-text_rank")[:20]
        )
        return Response({"results": [_knowledge_chunk_dict(chunk) for chunk in chunks]})


class MeshLoopsAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectMemberPermission]

    def get(self, request, slug, project_id):
        loops = MeshLoopDefinition.objects.filter(project_id=project_id, deleted_at__isnull=True)
        return Response({"loops": [_loop_definition_dict(loop) for loop in loops]})


class MeshRunsAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectMemberPermission]

    def get(self, request, slug, project_id, run_id=None):
        runs = MeshLoopRun.objects.filter(project_id=project_id, deleted_at__isnull=True).select_related(
            "work_item", "definition"
        )
        if run_id:
            run = runs.filter(id=run_id).first()
            if not run:
                return Response({"error": "Run not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"run": _loop_run_dict(run, include_stages=True)})
        work_item_id = request.query_params.get("work_item_id")
        if work_item_id:
            runs = runs.filter(work_item_id=work_item_id)
        return Response({"runs": [_loop_run_dict(run) for run in runs[:100]]})


def _project_member(user_id, project_id):
    return ProjectMember.objects.select_related("project").get(
        project_id=project_id,
        member_id=user_id,
        is_active=True,
        deleted_at__isnull=True,
    )
