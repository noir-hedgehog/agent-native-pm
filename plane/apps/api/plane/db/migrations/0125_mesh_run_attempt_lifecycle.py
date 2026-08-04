# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db", "0124_seed_mesh_identity_and_roles")]

    operations = [
        migrations.AddField(
            model_name="meshrunattempt",
            name="provider_state",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="meshrunattempt",
            name="failure_code",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="meshrunattempt",
            name="failure_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="meshrunattempt",
            name="last_polled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="meshrunattempt",
            name="heartbeat_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="meshrunattempt",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(provider_run_id=""),
                fields=("provider", "provider_run_id"),
                name="mesh_attempt_unique_provider_run",
            ),
        ),
    ]
