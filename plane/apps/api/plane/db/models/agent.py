# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from .workspace import WorkspaceBaseModel


class AgentRegistrationApplication(WorkspaceBaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    agent_id = models.CharField(max_length=64)
    display_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    requested_role = models.CharField(max_length=16, default="member")
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=32, default="bootstrap")
    reviewed_by = models.ForeignKey(
        "db.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="reviewed_agent_applications",
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "agent_registration_applications"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "agent_id"],
                condition=models.Q(status="pending", deleted_at__isnull=True),
                name="unique_pending_agent_application",
            )
        ]
