# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re

from celery import shared_task
from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.utils import timezone

from plane.db.models import MeshKnowledgeChunk, MeshKnowledgeDocument, Page, PageVersion
from plane.mesh.source_formats import sha256_text


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@shared_task(queue="mesh-indexer")
def index_mesh_page(page_id: str):
    page = Page.objects.filter(id=page_id, deleted_at__isnull=True).first()
    if not page:
        return {"status": "missing", "page_id": page_id}
    project = page.projects.filter(project_pages__deleted_at__isnull=True).first()
    if not project:
        return {"status": "not_project_page", "page_id": page_id}
    source = page.source_text if page.source_format in {"markdown", "yaml"} else (page.description_stripped or "")
    checksum = sha256_text(source)
    page_version = PageVersion.objects.filter(page=page, deleted_at__isnull=True).order_by("-last_saved_at").first()
    with transaction.atomic():
        document, _ = MeshKnowledgeDocument.objects.update_or_create(
            page=page,
            checksum=checksum,
            defaults={
                "workspace_id": page.workspace_id,
                "project_id": project.id,
                "page_version": page_version,
                "index_status": MeshKnowledgeDocument.IndexStatus.INDEXING,
                "index_error": "",
            },
        )
        MeshKnowledgeChunk.objects.filter(document=document, deleted_at__isnull=True).delete()
        chunks = [
            MeshKnowledgeChunk(
                workspace_id=page.workspace_id,
                project_id=project.id,
                document=document,
                heading=heading,
                content=content,
                sort_order=index,
            )
            for index, (heading, content) in enumerate(_split_markdown(source))
            if content.strip()
        ]
        MeshKnowledgeChunk.objects.bulk_create(chunks)
        MeshKnowledgeChunk.objects.filter(document=document).update(
            content_search=SearchVector("heading", weight="A") + SearchVector("content", weight="B")
        )
        document.index_status = MeshKnowledgeDocument.IndexStatus.DEGRADED
        document.index_error = "Semantic embedding is not configured; PostgreSQL full-text search is active."
        document.indexed_at = timezone.now()
        document.save(update_fields=["index_status", "index_error", "indexed_at", "updated_at"])
    return {"status": document.index_status, "document_id": str(document.id), "chunks": len(chunks)}


def _split_markdown(source: str) -> list[tuple[str, str]]:
    heading = ""
    lines: list[str] = []
    chunks: list[tuple[str, str]] = []
    for line in source.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if lines:
                chunks.append((heading, "\n".join(lines).strip()))
            heading = match.group(2).strip()
            lines = []
        else:
            lines.append(line)
    if lines or heading:
        chunks.append((heading, "\n".join(lines).strip()))
    return chunks or [("", source)]
