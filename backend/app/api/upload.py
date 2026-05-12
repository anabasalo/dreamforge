"""HTTP handler for document upload.

POST /upload accepts one or more multipart files. The request is
atomic: either every file is ingested into the dreamspace or none is
(the chunk-cap and duplicate-name checks happen before any write).

The graph rebuild that Phase 2 will hook in here is a TODO; for now the
response carries ``snapshot: null``.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_embedder, get_settings_dep, get_vector_store
from app.config import Settings
from app.core.embedders import Embedder
from app.core.ingestion import ingest_batch
from app.db.vector_store import VectorStore
from app.schemas import DocumentInfo, UploadResponse

router = APIRouter(tags=["upload"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_endpoint(
    files: list[UploadFile] = File(..., description="One or more PDF/MD/TXT files."),
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: Embedder = Depends(get_embedder),
    settings: Settings = Depends(get_settings_dep),
) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    # Stage all uploads to a single temp directory so the ingestion
    # pipeline sees real Path objects with original filenames. The temp
    # dir is deliberately *outside* the project tree so writing to it
    # does not trip uvicorn's --reload watcher.
    with tempfile.TemporaryDirectory() as tmp_dir:
        staged_paths: list[Path] = []
        for upload in files:
            if not upload.filename:
                raise HTTPException(status_code=400, detail="Every file must have a filename.")
            safe_name = Path(upload.filename).name  # strip any path traversal
            staged = Path(tmp_dir) / safe_name
            with staged.open("wb") as out_fp:
                shutil.copyfileobj(upload.file, out_fp)
            staged_paths.append(staged)

        result = ingest_batch(
            file_paths=staged_paths,
            vector_store=vector_store,
            embedder=embedder,
            max_chunks=settings.max_chunks_in_dreamspace,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    return UploadResponse(
        documents=[
            DocumentInfo(
                doc_id=d.doc_id,
                doc_name=d.doc_name,
                chunks_written=d.chunks_written,
            )
            for d in result.documents
        ],
        snapshot=None,  # Phase 2 will populate this with the graph rebuild stats.
        uploaded_at=result.uploaded_at,
    )
