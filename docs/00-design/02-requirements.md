# Requirements

This document is the contract the rest of the project implements
against. Items are intentionally small and testable.

## Functional requirements

### FR-1: Document ingestion

- **FR-1.1** The system accepts PDF, Markdown, and plain-text uploads.
- **FR-1.2** A single upload request can include one or more files.
- **FR-1.3** Each file is parsed into text, split into overlapping
  chunks, embedded, and stored in a vector database.
- **FR-1.4** Every chunk carries metadata at minimum: `chunk_id`,
  `doc_id`, `doc_name`, `chunk_index`, `source_type`, and
  `uploaded_at` (ISO 8601 timestamp).
- **FR-1.5** Re-ingesting a file with the same `doc_name` deletes the
  previous chunks for that document before inserting the new ones.
- **FR-1.6** The system enforces a hard cap on the total number of
  chunks held in the active dreamspace (default 800). Uploads that
  would exceed the cap fail with a clear error and no partial state.

### FR-2: Single global dreamspace

- **FR-2.1** The system holds exactly one active dreamspace at a
  time. There is no concept of named collections or per-user
  spaces. (See ADR 0007.)
- **FR-2.2** A successful upload extends the current dreamspace; the
  graph is recomputed over all chunks, not only the new ones.
- **FR-2.3** `POST /reset` deletes every chunk, every cached graph,
  and every uploaded raw file, returning the system to its empty
  state.

### FR-3: Semantic graph construction

- **FR-3.1** After every upload, the system computes a graph in
  which nodes are chunks and edges connect each chunk to its top-`k`
  most similar neighbors above a configurable similarity floor.
- **FR-3.2** The system clusters the chunks into a small number of
  groups using a density-based algorithm (HDBSCAN by default), and
  each non-noise cluster is assigned a stable cluster ID for the
  lifetime of the snapshot.
- **FR-3.3** The system computes a deterministic 3D position for
  every chunk using a dimensionality-reduction algorithm (UMAP
  with a fixed seed) so the layout is reproducible across reloads.
- **FR-3.4** For every non-noise cluster the system asks the LLM
  for a 1–3 word **theme label**. The noise cluster (HDBSCAN's
  `-1`) receives the label `"Outliers"` without an LLM call.
- **FR-3.5** The graph computation completes within ten seconds on a
  developer laptop for an upload of up to 200 chunks.

### FR-4: Graph retrieval

- **FR-4.1** `GET /graph` returns the most recent graph snapshot:
  list of nodes (id, doc_name, text preview, position, cluster id),
  list of edges (source, target, weight), and list of clusters
  (id, theme label, color, size).
- **FR-4.2** When no upload has happened yet, `GET /graph` returns
  HTTP `204 No Content`.
- **FR-4.3** A graph snapshot survives backend restarts. After
  restart, `GET /graph` serves the most recent on-disk snapshot
  without recomputing.

### FR-5: Dream generation

- **FR-5.1** `POST /dream` returns an LLM-generated narrative that
  interprets the document set as a whole. The narrative references
  cluster theme labels by name.
- **FR-5.2** The request accepts a `temperature` in `[0.0, 1.0]`
  (default 0.7) which is passed through to the LLM and visibly
  changes the character of the output.
- **FR-5.3** The response includes the narrative text and a list of
  cluster IDs the narrative emphasizes, so the frontend can
  highlight them in the 3D scene.
- **FR-5.4** Calling `/dream` when the dreamspace is empty returns
  HTTP `409 EmptyDreamspace`.

### FR-6: Relationship explanation

- **FR-6.1** `POST /explain` accepts two identifiers and returns a
  short paragraph explaining why they are semantically connected.
  An identifier is either a chunk ID or `cluster:<id>`.
- **FR-6.2** Both identifiers must reference entities present in the
  current snapshot; otherwise the request fails with HTTP `404`.
- **FR-6.3** The explanation is grounded in the actual chunk texts
  for chunk identifiers, and in representative chunks of the cluster
  for cluster identifiers.

### FR-7: Frontend interaction

- **FR-7.1** The frontend renders the graph as an interactive
  three-dimensional force-directed scene.
- **FR-7.2** Nodes are colored by cluster, and a legend shows
  cluster theme labels and their colors.
- **FR-7.3** Clicking a node opens a side panel showing the chunk
  text, source filename, and top neighbors.
- **FR-7.4** A central control surface exposes the **Dream** button
  and the temperature slider; pressing **Dream** displays the
  narrative and pulses the emphasized clusters in the 3D scene.
- **FR-7.5** A **Reset** control calls `POST /reset` and returns
  the page to its empty state.
- **FR-7.6** When the backend is unreachable, the frontend shows a
  visible error state rather than failing silently.

## Non-functional requirements

### NFR-1: Performance

- **NFR-1.1** Graph computation (similarity, k-NN, HDBSCAN, UMAP,
  theme labels) completes in under ten seconds on a developer
  laptop for up to 200 chunks. Theme-label LLM calls are made in
  parallel where possible.
- **NFR-1.2** `GET /graph` responds in under 200 ms (cached payload).
- **NFR-1.3** `POST /dream` responds in under five seconds at
  default temperature on the Groq free tier.
- **NFR-1.4** The 3D scene renders at a smooth frame rate
  (≥30 fps target, 60 fps on recent hardware) for graphs up to
  500 nodes.
- **NFR-1.5** Embeddings are computed once at ingestion and reused
  for all subsequent graph computations, dream calls, and
  explanations.

### NFR-2: Reliability

- **NFR-2.1** Failures of the LLM during theme labeling do not
  break ingestion: clusters fall back to a generic label
  (`Cluster N`) and the graph still ships.
- **NFR-2.2** A failure of the LLM during `/dream` or `/explain`
  returns HTTP `502 LLMUnavailable` with a clear error body, after
  one retry.
- **NFR-2.3** Empty results, unknown identifiers, and malformed
  uploads return clear HTTP error codes (`400`, `404`, `409`,
  `422`, `502`) rather than 500s.

### NFR-3: Maintainability

- **NFR-3.1** The backend is layered: HTTP handlers under
  `backend/app/api/`, business logic under `backend/app/core/`,
  persistence under `backend/app/db/`, and LLM access under
  `backend/app/llm/`. ChromaDB is imported only from `db/`.
- **NFR-3.2** The LLM is accessed through an `LLMClient` Protocol
  so providers can be swapped without touching `core/`.
- **NFR-3.3** Configuration is centralized in
  `backend/app/config.py` (Pydantic Settings) and loaded from
  environment variables.
- **NFR-3.4** Backend lint passes (`ruff`) and the test suite is
  green in CI on every push.
- **NFR-3.5** Frontend `tsc --noEmit` and `npm run build` succeed
  in CI on every push.

### NFR-4: Cost

- **NFR-4.1** The system runs at zero monetary cost on free tiers
  and open-source components. No paid APIs are required.

### NFR-5: Reproducibility

- **NFR-5.1** A single `docker compose up` (with a populated
  `.env`) brings up the backend and frontend services from a
  fresh clone.
- **NFR-5.2** ChromaDB and the graph cache are persisted via
  mounted volumes so state survives container restarts.
- **NFR-5.3** Graph layout is deterministic for a given
  `(chunks, embeddings, seed)` triple. The same upload produces
  the same 3D positions.

### NFR-6: Accessibility (target, not strict)

- **NFR-6.1** The application provides a non-3D fallback view (a
  flat list of clusters and chunks) for users who cannot use
  WebGL. *Target for Phase 5; not a release blocker.*
- **NFR-6.2** All interactive controls are operable from the
  keyboard. *Best-effort.*

## Non-requirements (explicitly out of scope)

- authentication, authorization, multi-user accounts
- multiple coexisting dreamspaces
- token streaming (dream narrative arrives in one response, even
  though the UI may animate its reveal client-side)
- horizontal scaling, load balancing, autoscaling
- multi-version document history
- monitoring dashboards (Prometheus, Grafana, OpenTelemetry)
- fine-tuning of embedding or generation models
- GPU support
- a question-answering / chat surface

## Acceptance test (Phase 5 milestone)

A reviewer should be able to, from a clean clone:

1. populate `.env` from `.env.example`,
2. run `docker compose up`,
3. open `http://localhost:5173`,
4. drop the four sample documents in `backend/data/raw/sample/` into
   the page,
5. observe a 3D graph with at least three labeled clusters appear
   within ten seconds,
6. click a node, read its chunk text and neighbors in the side
   panel,
7. press **Dream** at temperature 0.3 and again at 0.9, observing
   that both narratives reference real cluster themes and that the
   character of the output visibly differs,
8. ask `/explain` for two nodes from different clusters and read a
   grounded paragraph,
9. press **Reset** and observe the page return to the empty state.

If all nine steps succeed, the project meets its requirements.
