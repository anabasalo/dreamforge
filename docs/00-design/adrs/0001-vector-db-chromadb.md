# ADR 0001 — Use ChromaDB as the vector store

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

The system needs a vector store to hold chunk embeddings and let the
graph engine read them all back at graph-build time. Requirements
relevant to this decision:

- runs locally with no paid services
- persists to disk between restarts
- supports per-chunk metadata (`doc_id`, `doc_name`, `chunk_index`,
  `source_type`, `uploaded_at`, `char_count`)
- has a Python client and modest setup overhead
- needs to support a `get_all_chunks_with_embeddings()` style read
  (not just nearest-neighbor search) so the graph engine can run
  similarity over the full corpus
- comfortably holds up to a few hundred chunks (the
  `MAX_CHUNKS_IN_DREAMSPACE` cap is 800)

## Decision

Use **[ChromaDB](https://www.trychroma.com/)** in **embedded
(in-process) mode**, with the persistent store at
`backend/data/chroma/`.

The ChromaDB client is wrapped behind `backend/app/db/vector_store.py`.
No other module imports `chromadb` directly. This keeps the choice
swappable.

The dreamspace uses exactly one collection, named `dreamforge`,
created lazily on first ingest. The "named collections" feature of
Chroma is intentionally unused (see ADR 0007).

## Consequences

**Positive**:

- Zero infrastructure: ChromaDB runs in the same Python process as
  FastAPI. No separate service to start.
- Persistence is a single directory we mount as a Docker volume.
- The Python API exposes both metadata storage and bulk reads,
  which is exactly what the graph engine needs.
- Active OSS project with good docs.

**Negative / accepted trade-offs**:

- Embedded mode is single-process. Two concurrent uploads from
  different browsers will serialize at the FastAPI worker. Acceptable
  given the single-user product framing.
- The on-disk format is internal to Chroma; backing up means copying
  the directory.
- Bulk reads (`get(include=["embeddings", "metadatas", "documents"])`)
  load everything into memory at once. At 800 chunks this is trivial;
  at 100k it would not be.

## Alternatives considered

### FAISS

- *Pros:* extremely fast, mature, no service.
- *Cons:* index-only — no built-in metadata store. We would have to
  bolt on SQLite for metadata. The graph engine would also need a
  separate code path to enumerate vectors. More moving parts than
  Chroma.

### Pinecone

- *Pros:* managed, fast, scales effortlessly.
- *Cons:* paid (free tier exists but is usage-limited and requires
  an account), and adds a network dependency. Conflicts with NFR-4
  (zero cost) and NFR-5 (works from a clean clone with just Docker).

### Weaviate

- *Pros:* powerful (vector + keyword + GraphQL), self-hostable.
- *Cons:* heavier to operate (extra container, schema setup). The
  hybrid retrieval features Weaviate ships with are not used by
  this project — `dreamforge` does not do retrieval at all.

### pgvector (Postgres extension)

- *Pros:* uses a database many engineers already know.
- *Cons:* requires Postgres, which is another service. Setup cost
  exceeds the value at this scale.

### Qdrant

- *Pros:* fast, good metadata filtering, self-hostable.
- *Cons:* very close to Chroma in capabilities, but adds a separate
  service container. Chroma's embedded mode wins on simplicity.

### NumPy array + a JSON metadata file

- *Pros:* no dependency at all.
- *Cons:* re-implements Chroma's persistence, ID management, and
  metadata layer for no benefit. Risky.

## When we would revisit

- corpus regularly exceeds ~10k chunks (latency and memory pressure)
- multiple writer processes need to share state
- we need approximate nearest neighbors at scale (HNSW, IVF), in
  which case Qdrant or FAISS becomes worth the operational cost
