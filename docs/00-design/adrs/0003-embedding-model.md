# ADR 0003 — Use `all-MiniLM-L6-v2` for embeddings

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

The embedding model is the single most important quality knob for
the system: it decides what counts as "similar" in the semantic
graph. Requirements relevant to this decision:

- runs locally on CPU (no GPU required)
- small enough to fit in the Docker image without bloating it
- fast enough that ingestion of a few hundred chunks finishes in
  seconds, not minutes
- output dimensionality small enough to make k-NN over a few
  hundred chunks instant
- captures sentence-level semantic similarity well enough that
  HDBSCAN finds meaningful clusters
- free, with a permissive license

## Decision

Use **`sentence-transformers/all-MiniLM-L6-v2`**, loaded via the
`sentence-transformers` Python package, on CPU.

- Output dimension: **384**
- Approximate model size on disk: **~80 MB**
- Approximate throughput on a developer laptop: **>1000 sentences/second** on CPU
- License: Apache 2.0

The model name is exposed as `EMBED_MODEL` in `.env` so it can be
overridden, but the project standardizes on this default.

## Consequences

**Positive**:

- Tiny: the model fits comfortably inside the backend Docker image,
  and we can pre-download it at build time so the first request is
  fast.
- Fast: embedding hundreds of chunks at upload time is a non-issue
  on CPU.
- Well-understood: `all-MiniLM-L6-v2` is one of the most widely
  used sentence-transformers models and has a long track record on
  retrieval and clustering tasks.
- 384-dim vectors are small, which keeps the cosine matrix and
  UMAP step fast.

**Negative / accepted trade-offs**:

- Quality is good, not state-of-the-art. Larger models like
  `bge-large-en-v1.5` capture more nuance, especially across
  technical jargon and prose.
- 256-character chunks are short, and short text is exactly where
  MiniLM is *least* differentiated from larger models — but it is
  also where the absolute latency cost of larger models hurts most
  at upload time.
- Multilingual content is poorly served (the model is English-only).
  Documented as a known limit; out of scope for this version.

## Alternatives considered

### `BAAI/bge-small-en-v1.5`

- *Pros:* slightly better retrieval quality than MiniLM in benchmarks,
  similar size (~130 MB), 384-dim.
- *Cons:* very close call. We pick MiniLM because its track record
  on clustering tasks is longer and we will not invest in
  benchmarking the difference for this project.

### `BAAI/bge-large-en-v1.5`

- *Pros:* clearly higher quality on retrieval and clustering.
- *Cons:* ~1.3 GB, 1024-dim, much slower on CPU. A bad fit for the
  "single command, fresh laptop" target.

### OpenAI `text-embedding-3-small`

- *Pros:* very good quality, 1536-dim, no local model download.
- *Cons:* paid (per-token), conflicts with NFR-4. Adds a network
  dependency for ingestion. Not worth it given the chosen scope.

### `nomic-embed-text-v1`

- *Pros:* designed specifically for clustering and retrieval; long
  context support; good benchmarks.
- *Cons:* larger than MiniLM and slower on CPU; little practical
  upside for the chunk sizes and corpus sizes this project uses.

### TF-IDF / SVD baseline

- *Pros:* trivial, no model to download, deterministic.
- *Cons:* misses semantic similarity entirely (e.g. would fail to
  connect "log" in the Kafka chunk to "memory" in the Borges chunk).
  Defeats the whole point of the product.

## When we would revisit

- the project gains non-English content (we switch to a multilingual
  model like `paraphrase-multilingual-MiniLM-L12-v2`)
- chunk sizes increase to paragraph- or page-level (larger models
  start to pay off)
- we have evidence (visual, or via a small clustering benchmark)
  that MiniLM is producing weak clusters on representative documents
