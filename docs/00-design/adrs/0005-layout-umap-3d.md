# ADR 0005 — Seed the 3D layout with UMAP

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

The graph snapshot ships explicit `(x, y, z)` coordinates per node.
Those coordinates are the **initial positions** consumed by
`react-force-graph-3d`, which then runs a force-directed simulation
on top of them. Without good initial positions, force-directed
layouts on hundreds of nodes converge slowly and frequently produce
the dreaded "hairball" — a single dense ball with no visible
structure.

We therefore want a layout step that, given the embeddings, produces
a 3D arrangement that already *looks like* the semantic structure.
Requirements:

- preserves local structure (semantically close chunks land near
  each other)
- preserves global structure well enough that distinct themes form
  visibly distinct regions in 3D
- runs in a few seconds on CPU for hundreds of points
- is deterministic given a fixed seed (NFR-5.3)
- has a Python API and reasonable defaults

## Decision

Use **UMAP** (`umap-learn` package) with `n_components = 3`,
`metric = "cosine"`, and `random_state = 42` (configurable via the
`UMAP_SEED` setting), to project 384-dim embeddings to 3D. The
output coordinates are normalized into a fixed range and written
into the snapshot as `(x, y, z)`.

The force-directed renderer in the frontend uses these as starting
positions and applies its own springs/repulsion at runtime, with
small force constants so the renderer mostly *settles* the layout
rather than rewriting it.

## Consequences

**Positive**:

- UMAP captures both local and (reasonably well) global structure,
  so clusters identified by HDBSCAN typically appear as visibly
  separated regions in 3D.
- Deterministic with a fixed seed: the same upload yields the same
  galaxy, which is important for demos and screenshots.
- Fast on CPU for our sizes.
- The community of UMAP usage in embedding visualization is large;
  there is plenty of guidance for tuning if we need it later.

**Negative / accepted trade-offs**:

- UMAP coordinates are *not* a metric space we can interpret. We
  must not, for example, compute distances in UMAP space and use
  them as similarity. Any "is this connection real?" question goes
  back to the original embeddings.
- UMAP is non-convex; small changes in the input or in
  hyperparameters can change the layout shape (rotation,
  reflection). The `random_state` mitigates this for repeated runs
  on the same input but does not protect against re-tuning.
- 3D projections lose information vs. 2D in a different way: human
  perception of depth is weaker than of plane, so the bloom effect
  and node sizing matter more in 3D than in 2D.

## Alternatives considered

### t-SNE

- *Pros:* well-known, often produces visibly tight local clusters.
- *Cons:* notoriously bad at preserving global structure (clusters
  end up arbitrarily placed relative to each other), no reliable
  3D mode in common implementations, slower than UMAP, and the
  perplexity hyperparameter is a real knob to tune. UMAP is the
  modern default.

### PCA

- *Pros:* fast, deterministic, linear, easy to reason about.
- *Cons:* a 3-component PCA on 384-dim embeddings captures only
  the highest-variance directions; cluster separation is usually
  poor and the layout looks flat. Useful as a sanity check, not
  as the primary layout.

### Force-directed only (no seed)

- *Pros:* one fewer dependency.
- *Cons:* converges slowly and frequently produces a hairball on
  hundreds of nodes. The user would see the graph "untangle" for
  several seconds, which is exactly the wrong impression.

### MDS (multidimensional scaling)

- *Pros:* respects pairwise distances directly.
- *Cons:* O(n²) memory and worse global behavior than UMAP at our
  sizes; not used in practice for embedding visualization.

### Pre-baked spherical layout per cluster

- *Pros:* visually clean, very fast.
- *Cons:* cluster boundaries dominate over genuine inter-cluster
  proximity. Two semantically close chunks in *different* clusters
  would not appear close. Defeats the point of the graph.

### TriMap or PaCMAP (UMAP successors)

- *Pros:* arguably better global structure preservation than UMAP
  in some benchmarks.
- *Cons:* much smaller community, less mature Python packaging.
  We may experiment later, but UMAP is the safe default.

## When we would revisit

- visible cases where two semantically related chunks (verified by
  cosine similarity) are placed far apart in the 3D layout, even
  after the renderer settles
- the corpus exceeds the size where UMAP fits comfortably (~10k
  points) and we need a faster alternative (PaCMAP or
  approximate UMAP)
- we want stable layouts under incremental upload (UMAP cannot do
  this without retraining; an online algorithm would be needed)
