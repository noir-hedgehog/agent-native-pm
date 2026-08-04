# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
from datetime import timedelta

from django.http import JsonResponse
from django.db import connection
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_GET

from plane.db.models import MeshRunAttempt


@require_GET
def mesh_index(request):
    environment = os.environ.get("MESH_ENVIRONMENT", "development")
    return JsonResponse(
        {
            "name": "Mesh",
            "service": "mesh-console",
            "environment": environment,
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
    database = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database = "error"
    stale_cutoff = timezone.now() - timedelta(
        seconds=max(int(os.environ.get("MESH_STALE_ATTEMPT_SECONDS", "180")), 60)
    )
    stale_attempts = (
        MeshRunAttempt.objects.filter(
            status=MeshRunAttempt.Status.RUNNING,
            deleted_at__isnull=True,
        )
        .filter(Q(heartbeat_at__lt=stale_cutoff) | Q(heartbeat_at__isnull=True, started_at__lt=stale_cutoff))
        .count()
        if database == "ok"
        else None
    )
    return JsonResponse(
        {
            "status": "ok" if database == "ok" and stale_attempts == 0 else "degraded",
            "service": "mesh-console",
            "environment": os.environ.get("MESH_ENVIRONMENT", "development"),
            "database": database,
            "stale_attempts": stale_attempts,
        }
    )
