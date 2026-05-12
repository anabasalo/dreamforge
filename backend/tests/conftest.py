"""Shared pytest fixtures.

Tests use a deterministic fake embedder, a per-test ChromaDB directory,
and a per-test raw-upload directory so the suite is fast, offline, and
isolated. The real sentence-transformers model is never loaded under
pytest, and no network is hit.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import pytest


# ---- filesystem fixtures ----


@pytest.fixture
def tmp_chroma_dir(tmp_path: Path) -> Path:
    """A clean ChromaDB persistence directory per test."""
    persist = tmp_path / "chroma"
    persist.mkdir()
    return persist


@pytest.fixture
def tmp_raw_dir(tmp_path: Path) -> Path:
    """A clean raw-upload staging directory per test."""
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw


@pytest.fixture
def tmp_graphs_dir(tmp_path: Path) -> Path:
    """A clean graph-cache directory per test."""
    graphs = tmp_path / "graphs"
    graphs.mkdir()
    return graphs


@pytest.fixture
def make_doc(tmp_path: Path):
    """Factory: create a temp file with the given name and content."""

    def _make(name: str, content: str) -> Path:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    return _make


# ---- fake embedder ----


class _DeterministicEmbedder:
    """A reproducible fake embedder.

    Returns a ``dimension``-length vector derived from a hash of
    ``(text, index)``. Two distinct strings produce different vectors;
    the same string always produces the same vector.
    """

    def __init__(self, dimension: int = 32) -> None:
        self._dim = dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        out: list[float] = []
        for i in range(self._dim):
            digest = hashlib.sha256(f"{text}::{i}".encode()).digest()
            value = int.from_bytes(digest[:4], "big")
            # Map roughly to [-1, 1].
            out.append((value / (2**31)) - 1.0)
        return out

    @property
    def dimension(self) -> int:
        return self._dim


@pytest.fixture
def fake_embedder() -> _DeterministicEmbedder:
    return _DeterministicEmbedder()


# ---- fake LLM ----


@pytest.fixture
def fake_llm():
    from app.llm.fake import FakeLLMClient

    return FakeLLMClient()


# ---- API client with all deps overridden ----


@pytest.fixture
def client(tmp_chroma_dir, tmp_raw_dir, tmp_graphs_dir, fake_embedder, fake_llm):
    """A FastAPI TestClient with all external deps stubbed.

    - Vector store: real ChromaDB pointed at ``tmp_chroma_dir``
    - Embedder: deterministic fake (no model download)
    - LLM: ``FakeLLMClient`` (no Groq call)
    - Filesystem: tmp_raw_dir and tmp_graphs_dir override the defaults
    """
    from fastapi.testclient import TestClient

    from app.api.deps import (
        get_embedder,
        get_llm,
        get_settings_dep,
        get_vector_store,
    )
    from app.config import Settings
    from app.db.vector_store import VectorStore
    from app.main import create_app

    app = create_app()
    store = VectorStore(persist_dir=tmp_chroma_dir)

    test_settings = Settings(
        chroma_persist_dir=tmp_chroma_dir,
        graph_cache_dir=tmp_graphs_dir,
        raw_upload_dir=tmp_raw_dir,
        max_chunks_in_dreamspace=100,
    )

    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    app.dependency_overrides[get_llm] = lambda: fake_llm
    app.dependency_overrides[get_settings_dep] = lambda: test_settings

    test_client = TestClient(app)
    test_client.store = store  # type: ignore[attr-defined]
    test_client.fake_llm = fake_llm  # type: ignore[attr-defined]
    test_client.settings = test_settings  # type: ignore[attr-defined]
    return test_client
