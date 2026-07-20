# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.contrib.postgres.search import SearchVectorField
from django.db import models
from pgvector.django import VectorField

from .workspace import WorkspaceBaseModel


class MeshKnowledgeDocument(WorkspaceBaseModel):
    class IndexStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        INDEXING = "indexing", "Indexing"
        READY = "ready", "Ready"
        DEGRADED = "degraded", "Degraded"
        FAILED = "failed", "Failed"

    page = models.ForeignKey("db.Page", on_delete=models.CASCADE, related_name="mesh_knowledge_documents")
    page_version = models.ForeignKey(
        "db.PageVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="mesh_knowledge_documents"
    )
    checksum = models.CharField(max_length=64)
    index_status = models.CharField(max_length=16, choices=IndexStatus.choices, default=IndexStatus.PENDING)
    embedding_model = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    index_error = models.TextField(blank=True)

    class Meta:
        db_table = "mesh_knowledge_documents"
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["page", "checksum"],
                condition=models.Q(deleted_at__isnull=True),
                name="mesh_knowledge_document_unique_version",
            )
        ]


class MeshKnowledgeChunk(WorkspaceBaseModel):
    document = models.ForeignKey(MeshKnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    heading = models.CharField(max_length=512, blank=True)
    content = models.TextField()
    content_search = SearchVectorField(null=True)
    embedding = VectorField(dimensions=1536, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "mesh_knowledge_chunks"
        ordering = ("sort_order",)
        indexes = [models.Index(fields=["document", "sort_order"], name="mesh_knowledge_chunk_order")]
