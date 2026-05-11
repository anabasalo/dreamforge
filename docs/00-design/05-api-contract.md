# API contract

All endpoints are JSON over HTTP. The base URL in development is
`http://localhost:8000`. The full OpenAPI schema is also served at
`/docs` (Swagger UI) once the service is running.

## Conventions

- Request and response bodies are `application/json` unless otherwise
  noted (file upload uses `multipart/form-data`).
- All timestamps are ISO 8601 in UTC.
- Errors follow this shape:

  ```json
  {
    "error": "EmptyDreamspace",
    "message": "No documents have been uploaded yet.",
    "details": {}
  }
  ```

- HTTP status codes used: `200`, `201`, `204`, `400`, `404`, `409`,
  `422`, `502`, `500`.

## Endpoints

### `POST /upload`

Upload one or more files into the dreamspace. The graph is
recomputed over all chunks (existing + new) before the response
returns.

**Request** (`multipart/form-data`):

| field | type | required | description |
| --- | --- | --- | --- |
| `files` | file (repeated) | yes | one or more PDF, Markdown, or text files |

Example:

```bash
curl -X POST http://localhost:8000/upload \
  -F "files=@backend/data/raw/sample/kafka.md" \
  -F "files=@backend/data/raw/sample/attention.pdf"
```

**Response** `201 Created`:

```json
{
  "documents": [
    {
      "doc_id": "0a3f6c2e-...",
      "doc_name": "kafka.md",
      "chunks_written": 14
    },
    {
      "doc_id": "1c5b...",
      "doc_name": "attention.pdf",
      "chunks_written": 9
    }
  ],
  "snapshot": {
    "snapshot_id": "01HXYZ...",
    "stats": {
      "nodes": 142,
      "edges": 387,
      "clusters": 6,
      "computed_in_ms": 4321
    }
  },
  "uploaded_at": "2026-05-06T19:00:00.123Z"
}
```

**Errors**:

- `422 IngestionError` — at least one file could not be parsed (the
  whole batch is rejected, no partial state)
- `409 ChunkLimitExceeded` — the upload would exceed
  `MAX_CHUNKS_IN_DREAMSPACE`
- `400` — no files in the request

### `GET /graph`

Return the most recent graph snapshot. Used by the frontend to
render the 3D scene.

**Response** `200`:

```json
{
  "snapshot_id": "01HXYZ...",
  "computed_at": "2026-05-06T19:00:00.123Z",
  "config": {
    "embed_model": "all-MiniLM-L6-v2",
    "knn_k": 8,
    "sim_floor": 0.55,
    "hdbscan_min_cluster_size": 4,
    "umap_seed": 42
  },
  "stats": {"nodes": 142, "edges": 387, "clusters": 6, "computed_in_ms": 4321},
  "nodes": [
    {
      "id": "0a3f6c2e-...",
      "doc_id": "1c5b...",
      "doc_name": "kafka.md",
      "chunk_index": 3,
      "text_preview": "Kafka treats the log as the primary abstraction...",
      "x": 0.31, "y": -0.84, "z": 0.12,
      "cluster_id": 2,
      "degree": 7
    }
  ],
  "edges": [
    {"source": "0a3f6c2e-...", "target": "ad11b4...", "weight": 0.87}
  ],
  "clusters": [
    {"id": 2, "theme": "Persistence", "color": "#7c3aed", "size": 23, "centroid_chunk_ids": ["..."]},
    {"id": -1, "theme": "Outliers",   "color": "#6b7280", "size": 4,  "centroid_chunk_ids": []}
  ]
}
```

**Empty response** `204 No Content` — no upload has happened yet.

### `GET /chunks/{chunk_id}`

Return the full text of a chunk. Used by the side panel when a node
is clicked.

**Response** `200`:

```json
{
  "id": "0a3f6c2e-...",
  "doc_name": "kafka.md",
  "chunk_index": 3,
  "text": "Kafka treats the log as the primary abstraction. The log is an append-only, totally ordered sequence...",
  "char_count": 642,
  "neighbors": [
    {
      "id": "ad11b4...",
      "doc_name": "borges.txt",
      "weight": 0.74,
      "cluster_id": 4
    }
  ]
}
```

**Errors**: `404 EntityNotFound`.

### `POST /dream`

Generate an interpretive narrative across the current dreamspace.

**Request**:

```json
{
  "temperature": 0.7,
  "max_words": 220
}
```

| field | type | required | description |
| --- | --- | --- | --- |
| `temperature` | float | no | `[0.0, 1.0]`, default `0.7`. Passed through to the LLM. |
| `max_words` | int | no | soft target for narrative length, default `220`. |

**Response** `200`:

```json
{
  "narrative": "Across these documents, an idea of *persistence* keeps surfacing...",
  "emphasized_clusters": [2, 4, 0],
  "temperature": 0.7,
  "model": "llama-3.1-8b-instant",
  "latency_ms": 2840
}
```

**Errors**:

- `409 EmptyDreamspace` — the dreamspace has no chunks
- `502 LLMUnavailable` — the LLM call failed after one retry
- `400` — `temperature` out of range

### `POST /explain`

Explain why two entities are semantically connected. Each entity is
either a chunk ID or a cluster ID prefixed with `cluster:`.

**Request**:

```json
{
  "a": "0a3f6c2e-...",
  "b": "cluster:4"
}
```

| field | type | required | description |
| --- | --- | --- | --- |
| `a` | string | yes | chunk ID or `cluster:<id>` |
| `b` | string | yes | chunk ID or `cluster:<id>` |

**Response** `200`:

```json
{
  "a": "0a3f6c2e-...",
  "b": "cluster:4",
  "explanation": "The Kafka passage frames a log as continuity through time, which directly echoes the Memory cluster: both treat persistence as a defense against forgetting...",
  "model": "llama-3.1-8b-instant",
  "latency_ms": 1820
}
```

**Errors**:

- `404 EntityNotFound` — `a` or `b` is not in the current snapshot
- `502 LLMUnavailable` — the LLM call failed after one retry
- `400` — same chunk ID for `a` and `b`

### `POST /reset`

Delete every chunk, the graph snapshot, and the raw uploads, returning
the system to its empty state.

**Response** `204 No Content`.

### `GET /health`

Liveness check used by the frontend on boot.

**Response** `200`:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "chunks": 142,
  "has_snapshot": true,
  "embed_model": "all-MiniLM-L6-v2",
  "llm_model": "llama-3.1-8b-instant"
}
```

## Error catalog

| Code | HTTP | When raised |
| --- | --- | --- |
| `IngestionError` | 422 | parsing/chunking failed for at least one file |
| `ChunkLimitExceeded` | 409 | upload would exceed `MAX_CHUNKS_IN_DREAMSPACE` |
| `EmptyDreamspace` | 409 | `/dream` called with zero chunks |
| `EntityNotFound` | 404 | chunk or cluster id not in current snapshot |
| `LLMUnavailable` | 502 | LLM provider returned 5xx or timed out (after one retry) |
| `ValidationError` | 400 | Pydantic validation failed on request |

## CORS

The backend allows `CORS_ORIGINS` (default
`http://localhost:5173`). All endpoints support `OPTIONS` preflight.

## Versioning

The API is versioned implicitly as `v0` for the duration of the
project. Breaking changes during the build phases are allowed; once
Phase 5 ships, any further breaking change must bump the path
prefix to `/v1/...`.
