# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.db import models

from .workspace import WorkspaceBaseModel


class MeshSkill(WorkspaceBaseModel):
    class Visibility(models.TextChoices):
        PROJECT = "project", "Project"
        WORKSPACE = "workspace", "Workspace"

    slug = models.SlugField(max_length=128)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    page = models.ForeignKey("db.Page", on_delete=models.SET_NULL, null=True, blank=True, related_name="mesh_skills")
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PROJECT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_mesh_skills"
    )

    class Meta:
        db_table = "mesh_skills"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "project", "slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="mesh_skill_unique_slug",
            )
        ]


class MeshSkillVersion(WorkspaceBaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending review"
        PUBLISHED = "published", "Published"
        DEPRECATED = "deprecated", "Deprecated"
        REVOKED = "revoked", "Revoked"

    skill = models.ForeignKey(MeshSkill, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=64)
    source_text = models.TextField()
    manifest = models.JSONField(default=dict)
    checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    page_version = models.ForeignKey(
        "db.PageVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="mesh_skill_versions"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="submitted_mesh_skill_versions"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_mesh_skill_versions",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mesh_skill_versions"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["skill", "version"],
                condition=models.Q(deleted_at__isnull=True),
                name="mesh_skill_version_unique",
            )
        ]
