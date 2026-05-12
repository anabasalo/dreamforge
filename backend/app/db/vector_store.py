"""Thin ChromaDB wrapper for the single dreamspace.

This is the single place in the project that imports ``chromadb``. Every
other module sees only the ``VectorStore`` class and the value objects
exposed below.

See ADR 0001 for the choice of ChromaDB and ADR 0007 for why we use one
hardcoded collection instead of a collection-per-knowledge-base model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import chromadb

# The single collection name. The dreamspace is global; see ADR 0007.
COLLECTION_NAME = "dreamforge"

# Cosine similarity is what the graph engine expects. Configuring the
# HNSW index here keeps the choice in one place.
_HNSW_METADATA = {"hnsw:space": "cosine"}


@dataclass(frozen=True)
class StoredChunk:
    """A chunk as it lives in the vector store."""

    chunk_id: str
    doc_id: str
    doc_name: str
    chunk_index: int
    text: str
    metadata: dict
    embedding: list[float] | None = None


class VectorStore:
    """High-level wrapper over ChromaDB persistent storage.

    Exposes only the operations the rest of the project needs:
    counts, inserts, deletes, and a full enumeration of chunks (used by
    the graph engine in Phase 2).
    """

    def __init__(self, persist_dir: str | Path) -> None:
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))

    @property
    def persist_dir(self) -> Path:
        return self._persist_dir

    # --- collection lifecycle ---

    def _collection(self):
        return self._client.get_or_create_collection(
            name=COLLECTION_NAME, metadata=_HNSW_METADATA
        )

    def reset(self) -> None:
        """Delete every chunk from the dreamspace.

        Implemented as a delete-and-recreate so the underlying HNSW
        index is fresh; ChromaDB's incremental delete leaves orphan
        files we would rather not carry across uploads.
        """
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            # collection did not exist yet — no-op
            pass
        self._client.get_or_create_collection(
            name=COLLECTION_NAME, metadata=_HNSW_METADATA
        )

    # --- counts ---

    def count(self) -> int:
        """Total number of chunks currently in the dreamspace."""
        return self._collection().count()

    def count_doc(self, doc_name: str) -> int:
        """Number of chunks belonging to ``doc_name`` (0 if absent)."""
        coll = self._collection()
        result = coll.get(where={"doc_name": doc_name}, include=["metadatas"])
        metas = result.get("metadatas") or []
        return len(metas)

    def list_doc_names(self) -> list[str]:
        """Distinct ``doc_name`` values currently in the dreamspace."""
        coll = self._collection()
        result = coll.get(include=["metadatas"])
        metas = result.get("metadatas") or []
        names = {m.get("doc_name", "") for m in metas if m}
        return sorted(n for n in names if n)

    # --- writes ---

    def add_chunks(
        self,
        ids: Sequence[str],
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict],
    ) -> None:
        if not ids:
            return
        coll = self._collection()
        coll.add(
            ids=list(ids),
            documents=list(chunks),
            embeddings=[list(e) for e in embeddings],
            metadatas=list(metadatas),
        )

    def delete_doc(self, doc_name: str) -> int:
        """Delete every chunk where ``metadata.doc_name == doc_name``.

        Returns the number of chunks removed (0 if absent).
        """
        coll = self._collection()
        before = coll.count()
        coll.delete(where={"doc_name": doc_name})
        after = coll.count()
        return max(before - after, 0)

    # --- reads ---

    def get_chunk(self, chunk_id: str) -> StoredChunk | None:
        """Return one chunk by its id, or ``None`` if absent."""
        coll = self._collection()
        result = coll.get(ids=[chunk_id], include=["documents", "metadatas"])
        ids = result.get("ids") or []
        if not ids:
            return None
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        meta = dict(metas[0]) if metas and metas[0] else {}
        return StoredChunk(
            chunk_id=ids[0],
            doc_id=str(meta.get("doc_id", "")),
            doc_name=str(meta.get("doc_name", "")),
            chunk_index=int(meta.get("chunk_index", 0)),
            text=str(docs[0]) if docs else "",
            metadata=meta,
        )

    def get_all_chunks(self, include_embeddings: bool = False) -> list[StoredChunk]:
        """Return every chunk in the dreamspace.

        Used by the graph engine (Phase 2) to compute pairwise
        similarity, by ``/explain`` lookups, and by the
        ``/chunks/{id}`` endpoint when it needs neighbor info.
        """
        coll = self._collection()
        include = ["documents", "metadatas"]
        if include_embeddings:
            include.append("embeddings")
        result = coll.get(include=include)

        ids = result.get("ids") or []
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        embeddings = result.get("embeddings") if include_embeddings else None

        out: list[StoredChunk] = []
        for i, chunk_id in enumerate(ids):
            meta = dict(metas[i]) if i < len(metas) and metas[i] else {}
            emb: list[float] | None = None
            if include_embeddings and embeddings is not None and i < len(embeddings):
                emb = [float(x) for x in embeddings[i]]
            out.append(
                StoredChunk(
                    chunk_id=chunk_id,
                    doc_id=str(meta.get("doc_id", "")),
                    doc_name=str(meta.get("doc_name", "")),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    text=str(docs[i]) if i < len(docs) else "",
                    metadata=meta,
                    embedding=emb,
                )
            )
        return out
