# Alternatives — Phase 1

This page collects the choices made during Phase 1 and the
alternatives that were considered. The full Architecture Decision
Records live under [`docs/00-design/adrs/`](../00-design/adrs/); this
page summarizes them and adds a few smaller decisions that did not
warrant their own ADR.

## Chunking strategy

The chunker we ship is **fixed-size with overlap** and a boundary
preference (paragraph → sentence → newline) within a small window of
the target size. We pick boundaries when they are close to the
target, and we fall back to a hard character split otherwise. Default
size is 1024 characters (~256 tokens), overlap 120 characters.

| Alternative | Trade-off |
| --- | --- |
| **Semantic chunking** (split where embedding similarity drops) | Higher quality boundaries; ~10x slower at ingestion; adds a model call per split decision; harder to reason about. |
| **Recursive splitter** (LangChain-style: try paragraphs, then sentences, then words) | Similar in spirit to what we ship; we keep our own implementation to avoid the LangChain dependency for a 50-line function. |
| **Token-aware splitter** (count tokens with the embedding model's tokenizer) | Slightly more accurate sizing; requires loading the tokenizer at chunking time, which we avoid to keep ingestion fast and tokenizer-agnostic. We use chars as a 4:1 proxy for tokens, the standard heuristic for English. |
| **Whole-document embedding** | Trivial. Useless for a graph: one vector per doc gives you a graph with 4 nodes and no interesting structure. |

See ADR 0004 for the full reasoning, including the small-chunk
rationale specific to dreamforge.

## Vector store

We use **ChromaDB** in embedded (in-process) mode. The wrapper in
`backend/app/db/vector_store.py` is the only place that imports
`chromadb`, so the choice is swappable.

| Alternative | Trade-off |
| --- | --- |
| **FAISS** | Faster pure ANN; no metadata layer, would need SQLite alongside. More moving parts. |
| **Pinecone** | Managed; conflicts with the zero-cost constraint and adds a network dependency. |
| **Weaviate** | Powerful but heavier to operate. Hybrid retrieval features are unused by dreamforge. |
| **pgvector** | Familiar to many engineers; requires running Postgres just for this. |
| **Qdrant** | Very close to Chroma; adds a service container. |
| **NumPy + a JSON metadata file** | Re-implements Chroma without the test coverage. Risky. |

See ADR 0001.

## Embedding model

We use `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~80 MB,
CPU-friendly).

| Alternative | Trade-off |
| --- | --- |
| **`BAAI/bge-small-en-v1.5`** | Slightly better on retrieval benchmarks; same dimension; drop-in replacement. Worth trying as Exercise 2. |
| **`BAAI/bge-large-en-v1.5`** | Higher quality, 1024-dim, ~1.3 GB. Bad fit for the "fresh laptop, no GPU" target. |
| **OpenAI `text-embedding-3-small`** | High quality; paid; network dependency. |
| **`nomic-embed-text-v1`** | Tuned for clustering; larger and slower on CPU; little upside for our chunk sizes. |
| **TF-IDF / SVD baseline** | Trivial; misses semantic similarity, which is exactly what we need. |

See ADR 0003.

## LLM provider

We default to **Groq** behind an `LLMClient` Protocol. The Protocol
is the important part: the rest of the project knows about `chat`,
not about Groq.

| Alternative | Trade-off |
| --- | --- |
| **OpenAI** | Best narrative quality; paid; the Protocol supports this as a drop-in for users who want better Dreams. |
| **Anthropic** | High quality on interpretive prompts; paid. |
| **Ollama (local)** | Free and offline; requires installing a separate runtime and pulling several GB of model weights; latency on CPU laptops is poor for the longer `/dream` call. |
| **`transformers` in-process** | No external service; bloats the Docker image by gigabytes; small models that fit on a laptop produce worse output than Groq's free tier. |
| **Multi-provider router (e.g. `litellm`)** | Useful if we supported many providers at once; we only need one at a time. |

See ADR 0002.

## Scoping model

dreamforge holds **one global dreamspace**. There is no collection
parameter and no concept of users.

| Alternative | Trade-off |
| --- | --- |
| **Named collections (rag-systems style)** | More flexibility; clutters the first-time experience with a "select dreamspace" step. |
| **Session-id dreamspaces** | Private per-browser; backend complexity goes up (per-session collections, caches, garbage collection). |
| **Authenticated multi-user** | The "real product" answer; doubles the surface area for no demo benefit. |

See ADR 0007.

## Smaller Phase 1 decisions

### Why staging uploads to a temp directory before ingestion?

`UploadFile` is a stream; the parser (`pdfplumber`) needs a real
file. Staging into a `tempfile.TemporaryDirectory()` with the
original filename means the pipeline can be unit-tested with
ordinary `Path` objects, and the temp directory is cleaned up
automatically when the request finishes.

A persistent copy of every upload also lands in `data/raw/`. This
costs disk but is cheap insurance: it means a user can re-ingest
after a crash or a manual recovery without having to find the
original files.

### Why a `count_doc(doc_name)` method on the vector store?

The transactional cap check needs to know "how many chunks will go
away when we replace this `doc_name`?". Doing this in one place keeps
the math in `ingest_batch` readable. An alternative was to compute
the delta from `get_all_chunks()` metadata, but that pulls every
embedding into memory just to count.

### Why hard-code the collection name `"dreamforge"`?

Because the dreamspace is global (ADR 0007). Making the collection
name a setting would invite the question "why not let users pick
it?", which leads to multi-dreamspace UX that we explicitly decided
against. We hard-code it in `db/vector_store.py` and document it
there.

### Why is `snapshot: null` allowed in the upload response?

Phase 1 has no graph engine. The schema reserves the snapshot field
so Phase 2 can fill it without changing the wire format. We
intentionally do *not* skip the field — surfacing `null` in the
contract today makes the Phase 2 change a non-event for any frontend
that has started consuming the endpoint.

### Why custom exceptions in `core/` instead of `HTTPException`?

Because layers below `api/` are testable as plain Python. Tests
exercise `ingest_batch` directly with a real ChromaDB and a fake
embedder; they would not work if the function raised
`fastapi.HTTPException`. The mapping happens in `app/main.py`, which
is the *only* place that knows about HTTP status codes.

### Why no `/upload` streaming progress?

Because the response is fast enough to keep the request open until
the writes finish (a few seconds at most, dominated by the first
embedder load). Streaming progress adds a websocket or SSE channel
and per-file state to the backend; the trade is not worth it at the
scale the cap enforces.
