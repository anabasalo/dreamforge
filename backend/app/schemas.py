"""Pydantic models for API requests and responses.

The shapes here are the ones documented in
``docs/00-design/05-api-contract.md``.

Phase 1 only ships the upload + ops surface. Phase 2 will add graph,
dream, and explain models alongside these.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---- Upload ----


class DocumentInfo(BaseModel):
    doc_id: str
    doc_name: str
    chunks_written: int


class SnapshotStats(BaseModel):
    """Summary of the graph rebuild that followed an upload.

    Phase 1 returns ``None`` for this field because the graph engine is
    not implemented yet; Phase 2 will populate it.
    """

    snapshot_id: str
    nodes: int
    edges: int
    clusters: int
    computed_in_ms: int


class UploadResponse(BaseModel):
    documents: list[DocumentInfo]
    snapshot: SnapshotStats | None = None
    uploaded_at: str


# ---- Ops ----


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    version: str
    chunks: int
    has_snapshot: bool
    embed_model: str
    llm_model: str


# ---- Error envelope ----


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict = Field(default_factory=dict)
