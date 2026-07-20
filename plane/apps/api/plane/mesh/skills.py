# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from plane.db.models import MeshSkill, MeshSkillVersion, Page, PageVersion, Project, ProjectPage, User
from plane.mesh.source_formats import ParsedSkill, parse_skill_markdown


@dataclass(frozen=True)
class SubmittedSkill:
    skill: MeshSkill
    version: MeshSkillVersion
    parsed: ParsedSkill


@transaction.atomic
def submit_skill_version(*, project: Project, user: User, source_text: str) -> SubmittedSkill:
    parsed = parse_skill_markdown(source_text)
    slug = str(parsed.manifest["name"]).strip().lower().replace(" ", "-")
    skill = MeshSkill.objects.filter(project=project, slug=slug, deleted_at__isnull=True).first()
    if skill and skill.versions.filter(version=parsed.manifest["version"], deleted_at__isnull=True).exists():
        raise ValueError("This Skill version already exists")

    page = skill.page if skill and skill.page_id else None
    if not page:
        page = Page.objects.create(
            workspace=project.workspace,
            owned_by=user,
            name=f"Skill: {parsed.manifest['name']}",
            source_format="markdown",
            source_text=source_text,
            external_source="mesh-skill",
            external_id=slug,
            created_by_id=user.id,
        )
        ProjectPage.objects.create(
            workspace=project.workspace,
            project=project,
            page=page,
            created_by_id=user.id,
        )
    else:
        page.name = f"Skill: {parsed.manifest['name']}"
        page.source_format = "markdown"
        page.source_text = source_text
        page.save(update_fields=["name", "source_format", "source_text", "updated_at"])

    page_version = PageVersion.objects.create(
        workspace=project.workspace,
        page=page,
        owned_by=user,
        source_format="markdown",
        source_text=source_text,
        created_by_id=user.id,
    )
    if not skill:
        skill = MeshSkill.objects.create(
            workspace=project.workspace,
            project=project,
            slug=slug,
            name=parsed.manifest["name"],
            description=parsed.manifest["description"],
            page=page,
            created_by=user,
        )
    elif not skill.page_id:
        skill.page = page
        skill.save(update_fields=["page", "updated_at"])
    version = MeshSkillVersion.objects.create(
        workspace=project.workspace,
        project=project,
        skill=skill,
        version=parsed.manifest["version"],
        source_text=source_text,
        manifest=parsed.manifest,
        checksum=parsed.checksum,
        status=MeshSkillVersion.Status.PENDING,
        page_version=page_version,
        submitted_by=user,
    )
    return SubmittedSkill(skill=skill, version=version, parsed=parsed)
