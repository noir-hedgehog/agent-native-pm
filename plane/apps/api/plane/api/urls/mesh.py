# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from plane.api.views import (
    MeshEligibleAgentsAPIEndpoint,
    MeshKnowledgeSearchAPIEndpoint,
    MeshLoopsAPIEndpoint,
    MeshProjectPolicyAPIEndpoint,
    MeshProjectRolesAPIEndpoint,
    MeshRunsAPIEndpoint,
    MeshSkillsAPIEndpoint,
    MeshWorkspaceEndpoint,
)


urlpatterns = [
    path("workspaces/<str:slug>/mesh/", MeshWorkspaceEndpoint.as_view(http_method_names=["get"]), name="mesh-api"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/roles/", MeshProjectRolesAPIEndpoint.as_view(http_method_names=["get"]), name="mesh-roles"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/eligible-agents/", MeshEligibleAgentsAPIEndpoint.as_view(http_method_names=["get"]), name="mesh-eligible-agents"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/policy/", MeshProjectPolicyAPIEndpoint.as_view(http_method_names=["get"]), name="mesh-policy"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/skills/", MeshSkillsAPIEndpoint.as_view(http_method_names=["get"]), name="mesh-skills"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/knowledge/search/", MeshKnowledgeSearchAPIEndpoint.as_view(http_method_names=["post"]), name="mesh-knowledge-search"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/loops/", MeshLoopsAPIEndpoint.as_view(http_method_names=["get"]), name="mesh-loops"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/runs/", MeshRunsAPIEndpoint.as_view(http_method_names=["get"]), name="mesh-runs"),
    path("workspaces/<str:slug>/mesh/projects/<uuid:project_id>/runs/<uuid:run_id>/", MeshRunsAPIEndpoint.as_view(http_method_names=["get"]), name="mesh-run"),
]
