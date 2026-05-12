# Phase 1 — Backend Foundation + Ingestion

## Learning goals

After this phase you will be able to:

- explain what an **embedding** is and why we store them next to the
  source text in a vector database
- explain why we **chunk** documents before embedding, and why
  dreamforge uses *smaller* chunks than a typical RAG project
- describe the **single-dreamspace** scoping model and why we delete
  before re-insert on every re-upload (idempotence)
- describe a **transactional batch upload**: every file in a request
  is either ingested or none is, even when only one of them is
  oversized
- design a small Python package where the choice of vector database
  and LLM provider can be swapped without touching the business logic

## What was built

| Path | Description |
| --- | --- |
| `backend/app/config.py` | Pydantic Settings loaded from `.env` |
| `backend/app/schemas.py` | API request/response models |
| `backend/app/core/exceptions.py` | Domain exceptions mapped to HTTP codes in `main.py` |
| `backend/app/core/embedders.py` | `Embedder` Protocol + `SentenceTransformerEmbedder` |
| `backend/app/core/ingestion.py` | Parsing, chunking, batch ingest, chunk-cap enforcement |
| `backend/app/db/vector_store.py` | ChromaDB wrapper for the single `dreamforge` collection |
| `backend/app/llm/base.py` | `LLMClient` Protocol (used by Phase 2+) |
| `backend/app/llm/groq_client.py` | Groq implementation of `LLMClient` |
| `backend/app/llm/fake.py` | Deterministic `FakeLLMClient` for tests |
| `backend/app/api/deps.py` | FastAPI dependency providers (process singletons) |
| `backend/app/api/upload.py` | `POST /upload` (multipart, one or more files) |
| `backend/app/api/ops.py` | `GET /health`, `POST /reset` |
| `backend/app/main.py` | FastAPI factory, CORS, exception to HTTP mapping |
| `backend/tests/conftest.py` | Fixtures: tmp dirs, fake embedder, fake LLM, `TestClient` |
| `backend/tests/test_ingestion.py` | Chunking, batch ingest, metadata, dedup, cap, reset |
| `backend/tests/test_api.py` | `/upload`, `/health`, `/reset`, error envelopes |
| `backend/data/raw/sample/` | Three short demo files (Kafka, attention, memory) |

## Walkthrough

The flow of a `POST /upload` request, end to end:

1. **HTTP layer** (`api/upload.py`)
   - FastAPI parses the `multipart/form-data` body into a list of
     `UploadFile` objects.
   - Each file is streamed to a temp directory using its original
     filename (the extension matters for the parser).
   - A persistent copy is also placed under `data/raw/` so a user can
     re-ingest after a manual recovery.
2. **Ingestion pipeline** (`core/ingestion.py`)
   - Each file is parsed to plain text (`pdfplumber` for PDFs,
     UTF-8 read for `.md` / `.txt`).
   - The text is split into overlapping chunks of ~1024 characters
     (~256 tokens) with ~120 characters of overlap. The splitter
     prefers paragraph, then sentence, then newline boundaries.
   - **Cap check (transactional).** Before any chunk is written, the
     total `(existing - being replaced) + incoming` is compared
     against `MAX_CHUNKS_IN_DREAMSPACE` (default 800). Exceeding the
     cap raises `ChunkLimitExceeded`; the dreamspace is unchanged.
   - **Dedup.** A duplicate `doc_name` within the same batch is
     rejected (you cannot upload two files with the same name in one
     request).
   - For each file: previous chunks under that `doc_name` are
     deleted, new chunks are embedded with `sentence-transformers`,
     and written to ChromaDB with metadata
     (`doc_id`, `doc_name`, `chunk_index`, `source_type`,
     `uploaded_at`, `char_count`).
3. **Persistence** (`db/vector_store.py`)
   - One collection, hardcoded as `dreamforge`. The HNSW index is
     configured for cosine similarity so the graph engine in
     Phase 2 can read embeddings back and run cosine directly.
4. **Response**
   - `201 Created` with the list of documents (each with a fresh
     `doc_id` and `chunks_written`), `uploaded_at`, and
     `snapshot: null` (the snapshot field will be filled by Phase 2's
     graph rebuild).

`GET /health` calls `vector_store.count()` and checks whether
`data/graphs/current.json` exists.

`POST /reset` deletes the Chroma collection, every file under
`data/graphs/`, and every file under `data/raw/`.

## How to run it

The instructions below assume you are in the `backend/` directory and
have Python 3.11+ installed.

### 1. Create a virtual environment and install dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # on Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

The first install takes a few minutes because `sentence-transformers`
pulls `torch`. You will *not* download the embedding model itself
until the first time the server actually embeds something.

### 2. Configure environment

```bash
cp .env.example .env
# The defaults are fine for Phase 1. The Groq API key is only used
# from Phase 2 onward, so it can stay empty for now.
```

### 3. Run the test suite

```bash
pytest -v
```

You should see roughly 20 tests pass in well under 10 seconds. None
of them hit the network or load the real `sentence-transformers`
model — the suite uses a deterministic `FakeEmbedder` and a
`FakeLLMClient`.

### 4. Start the API and try it manually

```bash
HF_HOME="$(pwd)/.cache/hf" uvicorn app.main:app --reload --reload-dir app
```

`--reload-dir app` is important: it tells uvicorn to watch *only*
the source tree under `app/` and ignore the `data/` directory.
Without it, ChromaDB writing to `data/chroma/` during an upload
would trigger an auto-reload that kills the in-flight request and
the upload silently produces an empty response. (Setting `HF_HOME`
controls where `sentence-transformers` caches the embedding model;
it is optional but keeps the ~80 MB download inside the project.)

Open `http://127.0.0.1:8000/docs` for an interactive Swagger UI.

```bash
# Liveness - should report 0 chunks on a fresh start.
curl http://127.0.0.1:8000/health

# Upload the three sample documents in one request.
# The FIRST call takes a few seconds because sentence-transformers
# downloads all-MiniLM-L6-v2 on demand; subsequent calls are fast.
curl -X POST http://127.0.0.1:8000/upload \
  -F "files=@data/raw/sample/kafka.md" \
  -F "files=@data/raw/sample/attention.md" \
  -F "files=@data/raw/sample/memory.txt"

# The dreamspace now has chunks.
curl http://127.0.0.1:8000/health

# Reset clears the dreamspace (the sample files under data/raw/sample/
# are kept so you can upload them again).
curl -X POST http://127.0.0.1:8000/reset
curl http://127.0.0.1:8000/health
```

## Exercises

1. **Chunk-size experiment.** Change `CHUNK_SIZE` in `.env` to `512`
   (about 128 tokens) and re-upload the three sample documents.
   How does the chunk count compare to the default 1024? Which
   setting do you think will produce a more interesting graph in
   Phase 2 — and why?
2. **Swap the embedder.** Set `EMBED_MODEL=BAAI/bge-small-en-v1.5`
   in `.env`. The output dimension still matches (384) so nothing
   else has to change. Notice how this is a one-line change because
   the rest of the code depends on `Embedder`, not on a specific
   model.
3. **Break the cap.** Set `MAX_CHUNKS_IN_DREAMSPACE=20` in `.env`,
   restart uvicorn, and try to upload all three sample docs at once.
   Confirm the API returns `409 ChunkLimitExceeded` *and* that the
   dreamspace is still empty afterwards (`/health` reports 0
   chunks).

## What's next

Phase 2 builds the **semantic graph engine** on top of the chunks
stored here: pairwise cosine, k-NN sparsification, HDBSCAN clusters,
UMAP-3D layout, and an LLM theme label per cluster. The new
`GET /graph` endpoint will return the snapshot, and `/upload` will
start populating the `snapshot` field that is currently `null`.

See [`docs/00-design/03-architecture.md`](../00-design/03-architecture.md)
for the full pipeline diagram.
