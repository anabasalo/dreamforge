# ADR 0004 — Cluster chunks with HDBSCAN (with a k-means fallback)

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

The graph engine needs to group chunks into a small number of
**themes**. Those themes are surfaced in the UI (one color and one
LLM-generated label per cluster) and feed the `/dream` and
`/explain` prompts. Requirements relevant to this decision:

- the number of themes is **not known in advance** — different
  document sets produce different counts
- the algorithm must tolerate documents that contribute outliers
  (a single fragment unrelated to anything else)
- the algorithm must be deterministic given the inputs (NFR-5.3)
- it must run quickly on the CPU side of an upload (NFR-1.1)
- it must work for corpora as small as a single document (under
  ~30 chunks) and as large as the cap (800 chunks)

## Decision

Use **HDBSCAN** (`hdbscan` Python package) as the primary clustering
algorithm, with a **k-means fallback** when HDBSCAN labels
everything as noise.

Settings:

- `min_cluster_size = 4` (configurable as `HDBSCAN_MIN_CLUSTER_SIZE`)
- `metric = "euclidean"` over L2-normalized embeddings (which is
  monotonic with cosine similarity — see "Notes on metric" below)
- `cluster_selection_method = "eom"` (Excess of Mass)
- `prediction_data = False` (we never predict cluster membership for
  unseen points; a re-upload triggers a full rebuild)

Fallback rule (in `core/graph_engine.py`):

```
if all(label == -1 for label in hdbscan_labels):
    k = max(2, int(round(sqrt(n_chunks))))
    fall back to KMeans(n_clusters=k, random_state=42)
    no noise cluster in this branch
```

The noise cluster (HDBSCAN's `-1`) is preserved as a real cluster
with `id = -1` and theme `Outliers`, but the LLM is not called for
it.

### Notes on metric

`sentence-transformers` outputs L2-normalized embeddings by default.
On normalized vectors, Euclidean distance and cosine distance are
monotonically related:

```
‖a - b‖² = 2 − 2·cos(a, b)
```

So clustering in Euclidean space over normalized embeddings produces
the same neighbor relationships as cosine, while letting us reuse
the well-tested Euclidean code path in `hdbscan`. We document this
explicitly because mixing metrics quietly is a common source of
confusion.

## Consequences

**Positive**:

- We do not have to pick `k` per upload. The same code handles a
  philosophy/AI mix that produces five themes and a tightly-scoped
  notes set that produces two.
- HDBSCAN's noise label cleanly separates "this chunk does not
  belong with anything else" from real clusters, which is exactly
  what the UI wants to communicate (the muted gray `Outliers`
  group).
- Deterministic given the embeddings, so the same upload reproduces
  the same clusters across runs.

**Negative / accepted trade-offs**:

- HDBSCAN occasionally returns *all-noise* on very small corpora
  with low density; the k-means fallback covers that case at the
  cost of producing arbitrary cluster boundaries.
- `min_cluster_size = 4` means a document that contributes only
  three closely-related chunks will not get its own cluster — it
  will join a related theme or be flagged as outliers. This is the
  correct behavior for our scope (we do not want one-chunk
  clusters).
- HDBSCAN parameter tuning is a real topic. We pick defaults that
  work on the demo corpus and document them; users who change
  document genres may need to re-tune.

## Alternatives considered

### k-means

- *Pros:* simple, fast, every engineer knows it.
- *Cons:* requires choosing `k` up front. Heuristics (silhouette,
  elbow) add complexity; and k-means produces convex, equal-density
  clusters which is the *wrong* prior for "natural themes". Used
  here only as the small-corpus fallback.

### Agglomerative hierarchical clustering

- *Pros:* no `k` required if cut at a threshold; produces a
  dendrogram that is conceptually nice.
- *Cons:* picking the cut threshold has the same problem as
  picking `k`. Slower than HDBSCAN at our sizes. HDBSCAN is
  essentially the modern, density-aware version of this idea.

### Community detection on the k-NN graph (Louvain / Leiden)

- *Pros:* operates directly on the graph we already build; no
  separate distance metric needed.
- *Cons:* requires picking a resolution parameter, which has the
  same flavor of "pick a knob" problem. Cluster boundaries
  depend on the k-NN topology, which can be fragile to small
  changes in the similarity floor. Worth revisiting later.

### DBSCAN

- *Pros:* density-based like HDBSCAN, simpler.
- *Cons:* requires choosing `eps` (the density radius). HDBSCAN
  was created specifically to remove that knob. Strictly worse
  for our use case.

### Spectral clustering

- *Pros:* well-understood theoretically.
- *Cons:* requires a fixed `k`, and is slow to compute the graph
  Laplacian on hundreds of points without justification.

## When we would revisit

- the corpus regularly produces all-noise even on real, varied
  documents (we tighten `min_cluster_size` or revisit the metric)
- we have a clear use case for *overlapping* themes (a chunk that
  belongs to two themes), in which case soft clustering or topic
  modeling (e.g. BERTopic) becomes interesting
- we want the graph topology itself to drive clusters (Leiden on
  the k-NN graph is the natural next step)
