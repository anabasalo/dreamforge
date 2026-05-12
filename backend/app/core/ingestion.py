"""Document ingestion: parse a file, split into chunks, embed, persist.

The dreamspace holds exactly one collection (see ADR 0007), so this
module never takes a ``collection`` argument. The vector store and the
embedder are passed in so this is unit testable without a real
ChromaDB or a real sentence-transformers model.

Metadata schema is defined in ``docs/00-design/04-data-model.md``.
Chunking decisions are recorded in ADR 0004.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.embedders import Embedder
from app.core.exceptions import ChunkLimitExceeded, IngestionError

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


@dataclass(frozen=True)
class IngestionResult:
    """One ingested document's outcome."""

    doc_id: str
    doc_name: str
    chunks_written: int
    source_type: str


@dataclass(frozen=True)
class BatchIngestionResult:
    """Aggregate of one /upload call (one or more documents)."""

    documents: list[IngestionResult]
    uploaded_at: str

    @property
    def total_chunks(self) -> int:
        return sum(d.chunks_written for d in self.documents)


# ---- chunking ----


def chunk_text(text: str, target_size: int = 1024, overlap: int = 120) -> list[str]:
    """Split ``text`` into overlapping chunks of ~``target_size`` characters.

    Within ±10 percent of the target size we look for, in priority order, a
    paragraph break, a sentence end, or a newline, and snap the split there.
    If none is available, we fall back to a hard character split with
    explicit overlap so a fact lying near the boundary is reachable via
    either neighbour chunk.

    Empty / whitespace-only input yields an empty list.
    """
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= target_size:
        raise ValueError("overlap must be smaller than target_size")

    text = (text or "").strip()
    if not text:
        return []

    n = len(text)
    if n <= target_size:
        return [text]

    chunks: list[str] = []
    start = 0
    backoff = max(1, target_size // 10)

    while start < n:
        end = start + target_size
        if end >= n:
            tail = text[start:].strip()
            if tail:
                chunks.append(tail)
            break

        window_lo = max(start + 1, end - backoff)
        window_hi = min(n, end + backoff)

        boundary = -1
        para = text.rfind("\n\n", window_lo, window_hi)
        if para > start:
            boundary = min(para + 2, n)
        else:
            sentence = text.rfind(". ", window_lo, window_hi)
            if sentence > start:
                boundary = min(sentence + 2, n)
            else:
                newline = text.rfind("\n", window_lo, window_hi)
                if newline > start:
                    boundary = min(newline + 1, n)

        if boundary != -1 and boundary > start:
            end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


# ---- single-document ingest (internal) ----


@dataclass(frozen=True)
class _PreparedDoc:
    """A document parsed and chunked but not yet written to the store."""

    doc_id: str
    doc_name: str
    source_type: str
    chunks: list[str]


def _prepare_document(path: Path) -> _PreparedDoc:
    if not path.exists():
        raise IngestionError(f"File not found: {path}")

    source_type = _infer_source_type(path)
    text = _parse_file(path, source_type)
    chunks = chunk_text(text)
    if not chunks:
        raise IngestionError(f"No content extracted from: {path.name}")

    return _PreparedDoc(
        doc_id=str(uuid.uuid4()),
        doc_name=path.name,
        source_type=source_type,
        chunks=chunks,
    )


# ---- batch ingest (the public entry point) ----


def ingest_batch(
    file_paths: Sequence[Path | str],
    vector_store,
    embedder: Embedder,
    *,
    max_chunks: int,
    chunk_size: int = 1024,
    chunk_overlap: int = 120,
) -> BatchIngestionResult:
    """Ingest one or more files into the single dreamspace collection.

    The whole batch is parsed and chunked first; if the resulting total
    plus the chunks already in the dreamspace would exceed ``max_chunks``,
    nothing is written. This gives transactional behavior for the batch
    (FR-1.6 in ``docs/00-design/02-requirements.md``).

    Within a batch, each ``doc_name``'s previous chunks are deleted before
    its new chunks are inserted, so a re-upload is idempotent (FR-1.5).
    """
    if not file_paths:
        raise IngestionError("No files were provided.")

    # Override chunk parameters for this call by binding them into a small
    # closure so _prepare_document's defaults stay simple.
    def _prep(path: Path) -> _PreparedDoc:
        if not path.exists():
            raise IngestionError(f"File not found: {path}")
        source_type = _infer_source_type(path)
        text = _parse_file(path, source_type)
        chunks = chunk_text(text, target_size=chunk_size, overlap=chunk_overlap)
        if not chunks:
            raise IngestionError(f"No content extracted from: {path.name}")
        return _PreparedDoc(
            doc_id=str(uuid.uuid4()),
            doc_name=path.name,
            source_type=source_type,
            chunks=chunks,
        )

    prepared: list[_PreparedDoc] = []
    for raw_path in file_paths:
        prepared.append(_prep(Path(raw_path)))

    # Capacity check across the batch. We count chunks that would be added
    # net of any same-name docs we are about to replace.
    existing_total = vector_store.count()
    replacing: dict[str, int] = {}
    for doc in prepared:
        if doc.doc_name in replacing:
            # The same filename appears twice in this batch — only the
            # *last* version will end up in the store. Reject loudly so the
            # caller does not get a silently truncated dreamspace.
            raise IngestionError(
                f"Duplicate filename in upload batch: '{doc.doc_name}'."
            )
        replacing[doc.doc_name] = vector_store.count_doc(doc.doc_name)
    incoming_total = sum(len(d.chunks) for d in prepared)
    net_after_replace = existing_total - sum(replacing.values()) + incoming_total
    if net_after_replace > max_chunks:
        raise ChunkLimitExceeded(
            current=existing_total, incoming=incoming_total, limit=max_chunks
        )

    uploaded_at = datetime.now(UTC).isoformat()
    results: list[IngestionResult] = []
    for doc in prepared:
        embeddings = embedder.embed(doc.chunks)
        metadatas = [
            {
                "doc_id": doc.doc_id,
                "doc_name": doc.doc_name,
                "chunk_index": i,
                "source_type": doc.source_type,
                "uploaded_at": uploaded_at,
                "char_count": len(doc.chunks[i]),
            }
            for i in range(len(doc.chunks))
        ]
        ids = [f"{doc.doc_id}:{i}" for i in range(len(doc.chunks))]

        # Idempotent re-ingest: an upload of the same doc_name replaces the
        # previous version's chunks (FR-1.5).
        vector_store.delete_doc(doc.doc_name)
        vector_store.add_chunks(
            ids=ids,
            chunks=doc.chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        results.append(
            IngestionResult(
                doc_id=doc.doc_id,
                doc_name=doc.doc_name,
                chunks_written=len(doc.chunks),
                source_type=doc.source_type,
            )
        )

    return BatchIngestionResult(documents=results, uploaded_at=uploaded_at)


# ---- parsing helpers ----


def _infer_source_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".md", ".markdown"):
        return "markdown"
    if ext == ".txt":
        return "text"
    raise IngestionError(
        f"Unsupported file extension: '{ext}'. "
        f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def _parse_file(path: Path, source_type: str) -> str:
    if source_type == "pdf":
        return _parse_pdf(path)
    return path.read_text(encoding="utf-8")


def _parse_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise IngestionError(
            "pdfplumber is required for PDF parsing. "
            "Install via `pip install pdfplumber`."
        ) from exc

    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            pages.append(page_text)

    return "\n\n".join(pages).strip()
