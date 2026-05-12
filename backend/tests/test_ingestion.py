"""Phase 1 unit tests: chunking, single-batch ingest, metadata, dedup, cap."""

from __future__ import annotations

import pytest

from app.core.exceptions import ChunkLimitExceeded, IngestionError
from app.core.ingestion import chunk_text, ingest_batch
from app.db.vector_store import VectorStore

# ---------- chunk_text ----------


def test_chunk_text_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunk_text_short_text_returns_single_chunk():
    text = "A short paragraph that fits well under the target size."
    chunks = chunk_text(text, target_size=1024, overlap=120)
    assert chunks == [text]


def test_chunk_text_long_text_splits_into_multiple():
    sentence = "This is a sentence. " * 200  # ~4000 chars
    chunks = chunk_text(sentence, target_size=512, overlap=64)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) > 0


def test_chunk_text_chunks_have_overlap_when_no_natural_boundary():
    # 5000 chars, no sentence/paragraph/newline boundaries.
    text = "abcdefghij" * 500
    chunks = chunk_text(text, target_size=1000, overlap=100)
    assert len(chunks) >= 4
    for i in range(len(chunks) - 1):
        tail = chunks[i][-100:]
        assert chunks[i + 1].startswith(tail), (
            f"overlap broken between chunk {i} and {i + 1}"
        )


def test_chunk_text_prefers_paragraph_boundary():
    para_a = "Apples. " * 150  # ~1200 chars
    para_b = "Bananas. " * 150  # ~1350 chars
    text = para_a.strip() + "\n\n" + para_b.strip()
    chunks = chunk_text(text, target_size=1300, overlap=100)
    assert len(chunks) >= 2
    # The first chunk should be dominated by Apples (paragraph 1).
    assert chunks[0].count("Apples") > chunks[0].count("Bananas")


def test_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text("anything", target_size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_text("anything", target_size=100, overlap=-1)


# ---------- ingest_batch ----------


def test_ingest_writes_chunks(tmp_chroma_dir, fake_embedder, make_doc):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    path = make_doc("hello.md", "Hello world. " * 200)

    result = ingest_batch(
        file_paths=[path],
        vector_store=store,
        embedder=fake_embedder,
        max_chunks=1000,
    )

    assert len(result.documents) == 1
    doc = result.documents[0]
    assert doc.doc_name == "hello.md"
    assert doc.source_type == "markdown"
    assert doc.chunks_written > 0
    assert store.count() == doc.chunks_written


def test_ingest_propagates_metadata(tmp_chroma_dir, fake_embedder, make_doc):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    path = make_doc("hello.md", "Hello world. " * 200)

    result = ingest_batch(
        file_paths=[path],
        vector_store=store,
        embedder=fake_embedder,
        max_chunks=1000,
    )
    doc = result.documents[0]

    stored = store.get_all_chunks()
    assert stored, "expected at least one chunk to come back"
    seen_indices = set()
    for chunk in stored:
        assert chunk.metadata["doc_id"] == doc.doc_id
        assert chunk.metadata["doc_name"] == "hello.md"
        assert chunk.metadata["source_type"] == "markdown"
        assert chunk.metadata["uploaded_at"] == result.uploaded_at
        assert chunk.metadata["char_count"] == len(chunk.text)
        idx = int(chunk.metadata["chunk_index"])
        assert 0 <= idx < doc.chunks_written
        seen_indices.add(idx)
    assert len(seen_indices) == doc.chunks_written


def test_ingest_unknown_extension_raises(tmp_chroma_dir, fake_embedder, make_doc):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    path = make_doc("notes.docx", "irrelevant")
    with pytest.raises(IngestionError):
        ingest_batch(
            file_paths=[path],
            vector_store=store,
            embedder=fake_embedder,
            max_chunks=1000,
        )


def test_ingest_missing_file_raises(tmp_chroma_dir, fake_embedder, tmp_path):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    with pytest.raises(IngestionError):
        ingest_batch(
            file_paths=[tmp_path / "does-not-exist.md"],
            vector_store=store,
            embedder=fake_embedder,
            max_chunks=1000,
        )


def test_ingest_empty_file_raises(tmp_chroma_dir, fake_embedder, make_doc):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    path = make_doc("empty.md", "   \n   \n  ")
    with pytest.raises(IngestionError):
        ingest_batch(
            file_paths=[path],
            vector_store=store,
            embedder=fake_embedder,
            max_chunks=1000,
        )


def test_ingest_multi_doc_one_call(tmp_chroma_dir, fake_embedder, make_doc):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    p1 = make_doc("first.md", "First doc text. " * 100)
    p2 = make_doc("second.md", "Second doc text. " * 100)

    result = ingest_batch(
        file_paths=[p1, p2],
        vector_store=store,
        embedder=fake_embedder,
        max_chunks=1000,
    )
    names = {d.doc_name for d in result.documents}
    assert names == {"first.md", "second.md"}

    stored_names = set(store.list_doc_names())
    assert stored_names == {"first.md", "second.md"}
    assert store.count() == result.total_chunks


def test_ingest_duplicate_in_same_batch_rejected(
    tmp_chroma_dir, fake_embedder, make_doc, tmp_path
):
    """Two files with the same filename in one batch is ambiguous."""
    store = VectorStore(persist_dir=tmp_chroma_dir)
    p1 = make_doc("dup.md", "first version. " * 50)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    p2 = other_dir / "dup.md"
    p2.write_text("second version. " * 50, encoding="utf-8")

    with pytest.raises(IngestionError):
        ingest_batch(
            file_paths=[p1, p2],
            vector_store=store,
            embedder=fake_embedder,
            max_chunks=1000,
        )


def test_reingest_replaces_chunks(tmp_chroma_dir, fake_embedder, make_doc):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    path_v1 = make_doc("foo.md", "Original content. " * 100)
    r1 = ingest_batch(
        file_paths=[path_v1],
        vector_store=store,
        embedder=fake_embedder,
        max_chunks=1000,
    )
    assert r1.documents[0].chunks_written > 0
    first_doc_id = r1.documents[0].doc_id

    # Overwrite the file in place and re-ingest the same name.
    path_v1.write_text("New content here. " * 50, encoding="utf-8")
    r2 = ingest_batch(
        file_paths=[path_v1],
        vector_store=store,
        embedder=fake_embedder,
        max_chunks=1000,
    )
    second_doc_id = r2.documents[0].doc_id
    assert second_doc_id != first_doc_id

    stored = store.get_all_chunks()
    assert stored
    for chunk in stored:
        assert chunk.metadata["doc_name"] == "foo.md"
        assert chunk.metadata["doc_id"] == second_doc_id
    assert store.list_doc_names() == ["foo.md"]


def test_ingest_respects_chunk_cap(tmp_chroma_dir, fake_embedder, make_doc):
    """A batch that would push the dreamspace past the cap is rejected,
    with no partial state."""
    store = VectorStore(persist_dir=tmp_chroma_dir)
    # First batch is fine.
    p1 = make_doc("a.md", "First. " * 200)
    ingest_batch(
        file_paths=[p1],
        vector_store=store,
        embedder=fake_embedder,
        max_chunks=100,
        chunk_size=300,
        chunk_overlap=30,
    )
    before = store.count()

    # Second batch is huge and exceeds the cap.
    p2 = make_doc("b.md", "Second. " * 5000)
    with pytest.raises(ChunkLimitExceeded):
        ingest_batch(
            file_paths=[p2],
            vector_store=store,
            embedder=fake_embedder,
            max_chunks=100,
            chunk_size=300,
            chunk_overlap=30,
        )

    # Nothing was added.
    assert store.count() == before
    assert "b.md" not in store.list_doc_names()


def test_reset_clears_everything(tmp_chroma_dir, fake_embedder, make_doc):
    store = VectorStore(persist_dir=tmp_chroma_dir)
    path = make_doc("a.md", "Some text. " * 100)
    ingest_batch(
        file_paths=[path],
        vector_store=store,
        embedder=fake_embedder,
        max_chunks=1000,
    )
    assert store.count() > 0

    store.reset()
    assert store.count() == 0
    assert store.list_doc_names() == []
