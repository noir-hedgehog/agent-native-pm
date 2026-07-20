# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.urls import path

from .views import mesh_health, mesh_index


urlpatterns = [
    path("", mesh_index, name="mesh-index"),
    path("health/", mesh_health, name="mesh-health"),
]
