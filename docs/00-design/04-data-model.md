# Data model

This document describes every persistent entity in the system, where
it lives, and how it is identified.

## Overview

Three kinds of state:

1. **Vector data** — chunks of documents and their embeddings, stored
   in ChromaDB at `backend/data/chroma/`.
2. **Graph snapshot** — a derived JSON file at
   `backend/data/graphs/current.json` (with an in-memory cache).
3. **Raw uploads** — original source files at `backend/data/raw/`,
   kept for re-ingestion after recovery.

There is no relational database. ChromaDB is the source of truth for
chunks and embeddings; the graph snapshot is derived data; raw
uploads are operational backup, not state read at request time.

## The single dreamspace

The system holds exactly one ChromaDB collection, named `dreamforge`,
created lazily on first ingest. There is no API surface for choosing
or naming collections (see ADR 0007). `POST /reset` deletes the
collection contents, the snapshot, and the raw uploads.

## Chunk schema

Every chunk stored in ChromaDB has four pieces of state:

| Field | Type | Owner | Description |
| --- | --- | --- | --- |
| `id` | string (UUID) | Chroma | unique chunk identifier |
| `document` | string | Chroma | the chunk text |
| `embedding` | float vector | Chroma | dense embedding (dim = model output, 384 for `all-MiniLM-L6-v2`) |
| `metadata` | dict | app | metadata fields (see below) |

### Metadata fields

These fields are written by `core/ingestion.py` for every chunk and
are queryable via Chroma `where` filters.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `doc_id` | string (UUID) | yes | stable id for the source document |
| `doc_name` | string | yes | original filename, e.g. `kafka.md` |
| `chunk_index` | int | yes | 0-based index of the chunk within the doc |
| `source_type` | string | yes | one of `pdf`, `markdown`, `text` |
| `uploaded_at` | string (ISO 8601) | yes | timestamp of ingestion |
| `char_count` | int | yes | length of the chunk text in characters (used for cap enforcement and UI previews) |

The chunk text itself is stored in Chroma's native `document` field,
not in metadata.

## Document identity

A document is identified by its `doc_name`. When the same `doc_name`
is re-uploaded, the existing chunks for that document are deleted
before the new ones are inserted. Each ingestion run also assigns a
fresh `doc_id` to the new version of the document; old chunks (which
had the previous `doc_id`) are removed.

This makes re-uploads idempotent and prevents duplicates.

## Graph snapshot schema

The graph snapshot is derived data. It is produced by the graph
engine after every successful upload, written atomically to
`backend/data/graphs/current.json`, and held in an in-memory cache
in `db/graph_cache.py`.

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
  "stats": {
    "nodes": 142,
    "edges": 387,
    "clusters": 6,
    "computed_in_ms": 4321
  },
  "nodes": [
    {
      "id": "0a3f6c2e-...",
      "doc_id": "1c5b...",
      "doc_name": "kafka.md",
      "chunk_index": 3,
      "text_preview": "Kafka treats the log as the primary abstraction...",
      "x": 0.31,
      "y": -0.84,
      "z": 0.12,
      "cluster_id": 2,
      "degree": 7
    }
  ],
  "edges": [
    {
      "source": "0a3f6c2e-...",
      "target": "ad11b4...",
      "weight": 0.87
    }
  ],
  "clusters": [
    {
      "id": 2,
      "theme": "Persistence",
      "color": "#7c3aed",
      "size": 23,
      "centroid_chunk_ids": ["0a3f6c2e-...", "..."]
    },
    {
      "id": -1,
      "theme": "Outliers",
      "color": "#6b7280",
      "size": 4,
      "centroid_chunk_ids": []
    }
  ]
}
```

Notes on the snapshot:

- `text_preview` is the first 240 characters of the chunk, used by
  the frontend for the legend and the side panel header. The full
  chunk text is fetched from ChromaDB on demand by the side panel.
- `x`, `y`, `z` are UMAP-3D coordinates **before** the force-directed
  renderer takes over. The renderer treats them as initial positions
  and then settles them with springs and repulsion.
- `cluster_id = -1` is HDBSCAN's noise label and is always present
  with `theme = "Outliers"` even if it has zero members (in which
  case the frontend hides it).
- `centroid_chunk_ids` are the up-to-five chunks closest to a
  cluster's centroid. They are reused by the LLM theme-labeling and
  dreaming prompts and exposed for tooling.
- `weight` is the cosine similarity of the chunk pair, in `[0, 1]`.
- `config` records the parameters the snapshot was computed with so
  a reader can tell why two snapshots differ.

## In-memory cache

`db/graph_cache.py` holds the most recent snapshot in a module-level
variable. The cache is the primary read path:

- `save(snapshot)` — write to disk atomically (`write current.json.tmp` → `rename`) and update the in-memory variable
- `load()` — return the in-memory variable; on a fresh process, hydrate from disk first; return `None` if neither has anything
- `clear()` — delete the on-disk file and reset the in-memory variable

The cache is invalidated only by:

- `POST /upload` — replaced with a new snapshot
- `POST /reset` — cleared

There is no time-based invalidation. The snapshot is correct as long
as the underlying ChromaDB has not changed, and only the API can
change it.

## Storage layout on disk

```
backend/data/
├── raw/                  # original uploaded source files (kept for recovery)
│   ├── kafka.md
│   ├── attention.pdf
│   ├── borges.txt
│   └── notes.md
├── chroma/               # ChromaDB persistent files (DO NOT EDIT BY HAND)
│   └── ...
└── graphs/
    └── current.json      # most recent graph snapshot
```

In Docker, `backend/data/` is a single mounted volume so all three
sub-directories survive restarts together.

## What is *not* in the data model

- no `User` entity (no auth)
- no `Tenant` / `Organization` / `Workspace` (one global dreamspace)
- no `Dream` history (every `/dream` call is independent; the
  frontend keeps the most recent narrative in component state but
  does not persist it)
- no `Explanation` cache (every `/explain` call hits the LLM)
- no document version history (re-upload replaces)
- no separate metadata DB (Chroma metadata is enough; snapshot is
  derived JSON)

## Capacity and limits

| Limit | Value | Why |
| --- | --- | --- |
| Total chunks in dreamspace | 800 | Keeps 3D scene at ≥30 fps on typical hardware; bounds LLM cost for theme labels |
| File size per upload | 10 MB | Practical for PDFs without long parser stalls |
| Chunk size (tokens) | 256 | Smaller than typical RAG chunks; richer graph topology (see ADR 0004) |
| Chunk overlap (tokens) | 30 | Keeps boundary facts reachable without ballooning the chunk count |
| `knn_k` | 8 | Each node connects to its top-8 neighbors above the floor |
| `sim_floor` | 0.55 | Below this, edges are noise on `all-MiniLM-L6-v2` |
| `hdbscan_min_cluster_size` | 4 | Allows small but meaningful themes |
| `umap_seed` | 42 | Determinism (NFR-5.3) |

These limits are settings; they live in `config.py` and can be
overridden via environment variables.
