# Glossary

A short reference for terms used throughout this project. Each entry
is one or two sentences and points at the doc where the concept is
explored more deeply.

---

**ADR (Architecture Decision Record).** A short document that captures
one significant architectural decision: its context, the decision,
the consequences, and the alternatives that were considered. ADRs in
this project live under `docs/00-design/adrs/`.

**Bloom (post-processing).** A rendering effect that adds a soft glow
around bright pixels. Used by `DreamGraph` to make the 3D scene feel
luminous. Discussed in Phase 3.

**Centroid (cluster).** The mean of a cluster's member embeddings.
The chunks closest to the centroid are used as representatives when
asking the LLM for a theme label or building the `/dream` prompt.

**Chunk.** A small piece of a document (a few hundred characters)
that is independently embedded and stored in the vector database.
The unit of representation in `dreamforge`. Smaller chunks than a
typical RAG system, because we want a richer graph topology. See
ADR 0004.

**Cluster.** A group of chunks that HDBSCAN considers densely
connected in embedding space. Each non-noise cluster gets a 1–3
word **theme** label from the LLM. The noise cluster
(`cluster_id = -1`) is labeled `Outliers` without an LLM call.

**Cosine similarity.** The cosine of the angle between two vectors.
The default similarity measure for our embeddings; high cosine means
semantically close. Values in `[0, 1]` after sentence-transformers
normalization.

**Dreamspace.** The current set of chunks the system holds. There
is exactly one at a time. Cleared by `POST /reset`. See ADR 0007.

**Dream temperature.** A `[0.0, 1.0]` slider exposed in the UI and
passed through to the LLM as its sampling temperature. Low values
produce factual synthesis; high values produce surreal, creative
narratives. Discussed in Phase 4.

**Embedding.** A fixed-length numeric vector that represents a piece
of text in a way that captures its meaning. Produced by an embedding
model (`all-MiniLM-L6-v2` by default, 384-dim). See ADR 0003.

**Force-directed layout.** A graph drawing algorithm that simulates
springs (along edges) and repulsion (between all nodes) until the
layout settles. `react-force-graph-3d` runs this continuously while
the user explores the scene. Discussed in Phase 3.

**Graph snapshot.** The serialized output of one full graph build:
nodes (with positions and cluster IDs), edges (with weights), and
clusters (with theme labels). Stored in memory and at
`backend/data/graphs/current.json`. Schema in
[`04-data-model.md`](./04-data-model.md).

**HDBSCAN.** A density-based clustering algorithm that finds clusters
of varying density and labels truly-isolated points as noise (`-1`).
Used by `dreamforge` for cluster discovery because, unlike k-means,
it does not require choosing `k` in advance. See ADR 0004.

**k-NN graph.** A sparse graph built by connecting each node to its
top-`k` most similar neighbors (above a similarity floor). The
sparsification step that turns an O(n²) similarity matrix into an
O(n·k) renderable graph. Discussed in Phase 2.

**LLM (Large Language Model).** The model that generates theme
labels, dream narratives, and relationship explanations. This
project uses Llama-3.1-8b-Instant via Groq by default, behind an
`LLMClient` Protocol. See ADR 0002.

**LLMClient Protocol.** A small Python `Protocol` (in
`backend/app/llm/base.py`) with a single `chat(system, user, ...)`
method. Lets the rest of the code stay provider-agnostic.

**LLM-as-interpreter.** The pattern this project uses: instead of
asking the LLM to *answer*, we ask it to *interpret* — name the
themes of a cluster, explain why two passages connect, weave a
narrative across a document set. Contrasted with chat / RAG /
classification uses of LLMs. Discussed in Phase 4.

**Noise (HDBSCAN).** Points that HDBSCAN considers not dense enough
to belong to any cluster. Always labeled `-1` and treated by
`dreamforge` as the `Outliers` cluster.

**Outliers cluster.** The single cluster with `id = -1`, label
`Outliers`, and a muted gray color. Holds whatever HDBSCAN
considered noise. Hidden in the UI when empty.

**Reset.** The single operation that returns the system to its
empty state: deletes every chunk, the graph snapshot, and the raw
uploads. Exposed as `POST /reset` and as a button in the UI.

**Sentence-transformers.** A library and family of models for
producing sentence-level embeddings, fine-tuned for semantic
similarity tasks. `dreamforge` uses `all-MiniLM-L6-v2` (384-dim,
~80 MB, runs on CPU). See ADR 0003.

**Similarity floor.** The minimum cosine similarity required for an
edge to exist. Below this, edges are dominated by noise. Default
`0.55`. Tunable per-build.

**Snapshot ID.** A monotonic identifier (ULID) assigned to each new
graph snapshot. Used by the frontend to detect that the underlying
graph has changed and refetch.

**Theme label.** A 1–3 word phrase the LLM produces to summarize a
cluster (e.g. `Persistence`, `Attention`, `Memory`). Visible in the
legend and used in the dream prompt. The noise cluster's theme is
always `Outliers`.

**UMAP.** Uniform Manifold Approximation and Projection — a
dimensionality-reduction algorithm. `dreamforge` uses it to project
384-dimensional embeddings down to 3D coordinates that seed the
force-directed renderer. Deterministic given a fixed seed. See
ADR 0005.

**Vector store / vector database.** A database optimized for storing
embeddings and answering nearest-neighbor queries quickly. This
project uses ChromaDB. See ADR 0001.
