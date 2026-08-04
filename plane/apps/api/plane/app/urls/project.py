# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import (
    ProjectViewSet,
    DeployBoardViewSet,
    ProjectInvitationsViewset,
    ProjectAgentMemberEndpoint,
    ProjectMemberViewSet,
    ProjectMemberUserEndpoint,
    ProjectJoinEndpoint,
    ProjectUserViewsEndpoint,
    ProjectIdentifierEndpoint,
    ProjectFavoritesViewSet,
    UserProjectInvitationsViewset,
    UserProjectRolesEndpoint,
    ProjectArchiveUnarchiveEndpoint,
    ProjectMemberPreferenceEndpoint,
    AgentPolicyApprovalEndpoint,
    AgentPolicyEndpoint,
    AgentPolicyHistoryEndpoint,
    AgentPolicyRuntimeEndpoint,
    MeshEligibleAgentsEndpoint,
    MeshKnowledgeSearchEndpoint,
    MeshLoopPublishEndpoint,
    MeshLoopStartEndpoint,
    MeshApprovalsEndpoint,
    MeshLoopsEndpoint,
    MeshMemberRolesEndpoint,
    MeshProjectPolicyEndpoint,
    MeshProjectRolesEndpoint,
    MeshRunsEndpoint,
    MeshSkillPublishEndpoint,
    MeshSkillsEndpoint,
    MeshStageAssignmentEndpoint,
)


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/loops/<uuid:loop_id>/start/",
        MeshLoopStartEndpoint.as_view(),
        name="mesh-loop-start",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/approvals/",
        MeshApprovalsEndpoint.as_view(),
        name="mesh-approvals",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/approvals/<uuid:approval_id>/",
        MeshApprovalsEndpoint.as_view(),
        name="mesh-approval-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/policy/",
        MeshProjectPolicyEndpoint.as_view(),
        name="mesh-project-policy",
    ),
    path(
        "workspaces/<str:slug>/projects/",
        ProjectViewSet.as_view({"get": "list", "post": "create"}),
        name="project",
    ),
    path(
        "workspaces/<str:slug>/projects/details/",
        ProjectViewSet.as_view({"get": "list_detail"}),
        name="project",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:pk>/",
        ProjectViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="project",
    ),
    path(
        "workspaces/<str:slug>/project-identifiers/",
        ProjectIdentifierEndpoint.as_view(),
        name="project-identifiers",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/invitations/",
        ProjectInvitationsViewset.as_view({"get": "list", "post": "create"}),
        name="project-member-invite",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/invitations/<uuid:pk>/",
        ProjectInvitationsViewset.as_view({"get": "retrieve", "delete": "destroy"}),
        name="project-member-invite",
    ),
    path(
        "users/me/workspaces/<str:slug>/projects/invitations/",
        UserProjectInvitationsViewset.as_view({"get": "list", "post": "create"}),
        name="user-project-invitations",
    ),
    path(
        "users/me/workspaces/<str:slug>/project-roles/",
        UserProjectRolesEndpoint.as_view(),
        name="user-project-roles",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/join/<uuid:pk>/",
        ProjectJoinEndpoint.as_view(),
        name="project-join",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/members/",
        ProjectMemberViewSet.as_view({"get": "list", "post": "create"}),
        name="project-member",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-members/",
        ProjectAgentMemberEndpoint.as_view(),
        name="project-agent-member",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-policy/",
        AgentPolicyEndpoint.as_view(),
        name="project-agent-policy",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-policy/history/",
        AgentPolicyHistoryEndpoint.as_view(),
        name="project-agent-policy-history",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-policy/runtime/",
        AgentPolicyRuntimeEndpoint.as_view(),
        name="project-agent-policy-runtime",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/agent-policy/approvals/<str:approval_id>/",
        AgentPolicyApprovalEndpoint.as_view(),
        name="project-agent-policy-approval",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/roles/",
        MeshProjectRolesEndpoint.as_view(),
        name="mesh-project-roles",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/members/<uuid:project_member_id>/roles/",
        MeshMemberRolesEndpoint.as_view(),
        name="mesh-member-roles",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/eligible-agents/",
        MeshEligibleAgentsEndpoint.as_view(),
        name="mesh-eligible-agents",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/skills/",
        MeshSkillsEndpoint.as_view(),
        name="mesh-skills",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/skills/versions/<uuid:version_id>/publish/",
        MeshSkillPublishEndpoint.as_view(),
        name="mesh-skill-publish",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/knowledge/search/",
        MeshKnowledgeSearchEndpoint.as_view(),
        name="mesh-knowledge-search",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/loops/",
        MeshLoopsEndpoint.as_view(),
        name="mesh-loops",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/loops/<uuid:loop_id>/publish/",
        MeshLoopPublishEndpoint.as_view(),
        name="mesh-loop-publish",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/stages/<uuid:stage_run_id>/assign/",
        MeshStageAssignmentEndpoint.as_view(),
        name="mesh-stage-assign",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/runs/",
        MeshRunsEndpoint.as_view(),
        name="mesh-runs",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/runs/<uuid:loop_run_id>/",
        MeshRunsEndpoint.as_view(),
        name="mesh-run-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/mesh/runs/<uuid:loop_run_id>/cancel/",
        MeshRunsEndpoint.as_view(),
        name="mesh-run-cancel",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/members/<uuid:pk>/",
        ProjectMemberViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-member",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/members/leave/",
        ProjectMemberViewSet.as_view({"post": "leave"}),
        name="project-member",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/project-views/",
        ProjectUserViewsEndpoint.as_view(),
        name="project-view",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/project-members/me/",
        ProjectMemberUserEndpoint.as_view(),
        name="project-member-view",
    ),
    path(
        "workspaces/<str:slug>/user-favorite-projects/",
        ProjectFavoritesViewSet.as_view({"get": "list", "post": "create"}),
        name="project-favorite",
    ),
    path(
        "workspaces/<str:slug>/user-favorite-projects/<uuid:project_id>/",
        ProjectFavoritesViewSet.as_view({"delete": "destroy"}),
        name="project-favorite",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/project-deploy-boards/",
        DeployBoardViewSet.as_view({"get": "list", "post": "create"}),
        name="project-deploy-board",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/project-deploy-boards/<uuid:pk>/",
        DeployBoardViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-deploy-board",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/archive/",
        ProjectArchiveUnarchiveEndpoint.as_view(),
        name="project-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/preferences/member/<uuid:member_id>/",
        ProjectMemberPreferenceEndpoint.as_view(),
        name="project-member-preference",
    ),
]
