"""Operational endpoints: /health and /reset.

``/health`` is the liveness check the frontend pings on boot.
``/reset`` wipes the dreamspace back to its empty state.
"""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, status

from app import __version__
from app.api.deps import get_settings_dep, get_vector_store
from app.config import Settings
from app.db.vector_store import VectorStore
from app.schemas import HealthResponse

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse)
def health_endpoint(
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_settings_dep),
) -> HealthResponse:
    try:
        chunks = vector_store.count()
    except Exception:  # noqa: BLE001 - liveness must always answer
        chunks = 0

    snapshot_file = settings.graph_cache_dir / "current.json"
    has_snapshot = snapshot_file.exists()

    return HealthResponse(
        status="ok",
        version=__version__,
        chunks=chunks,
        has_snapshot=has_snapshot,
        embed_model=settings.embed_model,
        llm_model=settings.llm_model,
    )


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_endpoint(
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Wipe every chunk and the graph snapshot.

    The shipped sample documents under ``data/raw/sample/`` are left
    alone so they remain available for the next upload.
    """
    vector_store.reset()

    if settings.graph_cache_dir.exists():
        for item in settings.graph_cache_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
