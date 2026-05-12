"""Phase 1 API tests: /upload, /health, /reset, error envelopes."""

from __future__ import annotations

import io


def _file(name: str, content: str) -> tuple[str, tuple[str, io.BytesIO, str]]:
    """Build a (field, (filename, BytesIO, content-type)) tuple for httpx."""
    return ("files", (name, io.BytesIO(content.encode("utf-8")), "text/plain"))


def test_health_reports_zero_chunks_on_fresh_dreamspace(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["chunks"] == 0
    assert body["has_snapshot"] is False
    assert body["embed_model"]
    assert body["llm_model"]
    assert body["version"]


def test_upload_single_file(client):
    resp = client.post("/upload", files=[_file("hello.md", "Hello world. " * 200)])
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["uploaded_at"]
    assert body["snapshot"] is None  # Phase 1: graph not built yet.
    assert len(body["documents"]) == 1
    doc = body["documents"][0]
    assert doc["doc_name"] == "hello.md"
    assert doc["chunks_written"] > 0
    assert doc["doc_id"]

    # /health now reflects the upload.
    health = client.get("/health").json()
    assert health["chunks"] == doc["chunks_written"]


def test_upload_multi_file(client):
    resp = client.post(
        "/upload",
        files=[
            _file("a.md", "Alpha content. " * 100),
            _file("b.md", "Beta content. " * 100),
        ],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    names = {d["doc_name"] for d in body["documents"]}
    assert names == {"a.md", "b.md"}
    total = sum(d["chunks_written"] for d in body["documents"])
    assert client.get("/health").json()["chunks"] == total


def test_upload_rejects_unsupported_extension(client):
    resp = client.post("/upload", files=[_file("notes.docx", "anything")])
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "IngestionError"
    assert "extension" in body["message"].lower()


def test_upload_rejects_when_no_files(client):
    """FastAPI's multipart validator surfaces the missing-files case."""
    resp = client.post("/upload")
    # FastAPI returns 422 for missing required form fields.
    assert resp.status_code == 422


def test_upload_enforces_chunk_cap(client):
    """With ``max_chunks_in_dreamspace=100`` from the test settings, a
    deliberately huge file is rejected with 409 ChunkLimitExceeded."""
    big_text = "x " * 200000  # >> 100 chunks of any reasonable size
    resp = client.post("/upload", files=[_file("huge.txt", big_text)])
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"] == "ChunkLimitExceeded"
    assert body["details"]["limit"] == 100
    # The dreamspace is unchanged.
    assert client.get("/health").json()["chunks"] == 0


def test_reset_clears_dreamspace(client):
    upload = client.post("/upload", files=[_file("a.md", "Some text. " * 100)])
    assert upload.status_code == 201
    assert client.get("/health").json()["chunks"] > 0

    resp = client.post("/reset")
    assert resp.status_code == 204

    health = client.get("/health").json()
    assert health["chunks"] == 0
    assert health["has_snapshot"] is False


def test_reingest_replaces_previous_chunks(client):
    """Re-uploading the same filename replaces the prior chunks."""
    r1 = client.post("/upload", files=[_file("foo.md", "Original content. " * 100)])
    assert r1.status_code == 201
    first = r1.json()["documents"][0]

    r2 = client.post("/upload", files=[_file("foo.md", "Very different. " * 30)])
    assert r2.status_code == 201
    second = r2.json()["documents"][0]
    assert second["doc_name"] == "foo.md"
    assert second["doc_id"] != first["doc_id"]

    # Total chunks reflect only the *new* version.
    assert client.get("/health").json()["chunks"] == second["chunks_written"]
