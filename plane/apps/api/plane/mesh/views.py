# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def mesh_index(request):
    return JsonResponse(
        {
            "name": "Mesh",
            "service": "mesh-console",
            "version": os.environ.get("MESH_VERSION", "development"),
            "based_on": "Plane Community Edition",
            "license": "AGPL-3.0-only",
            "source_url": os.environ.get("MESH_SOURCE_URL", "https://github.com/noir-hedgehog/mesh"),
            "health": "/mesh/health/",
            "mcp": "/api/v1/workspaces/{workspace_slug}/mcp/",
        }
    )


@require_GET
def mesh_health(request):
    return JsonResponse({"status": "ok", "service": "mesh-console"})
