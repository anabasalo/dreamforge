# ADR 0006 — Render the graph with `react-force-graph-3d`

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

The 3D galaxy is the entire point of the product. The visualization
layer must:

- render hundreds of nodes and edges interactively in the browser
- accept arbitrary node/edge data and update on uploads
- expose click and hover events on nodes and edges (so we can open
  the side panel and call `/explain`)
- support node coloring, sizing, and basic post-processing (bloom)
- run on Three.js so we can extend with custom shaders or effects
  later if we want to
- not require us to write a force-directed simulation from scratch

The frontend stack is React + TypeScript + Vite (chosen for the
ecosystem and developer ergonomics, not as a separately recorded
decision).

## Decision

Use **`react-force-graph-3d`** (which wraps `3d-force-graph`,
which wraps Three.js + `d3-force-3d`).

- the centerpiece component is `frontend/src/components/DreamGraph.tsx`,
  which renders `<ForceGraph3D ... />` and binds it to the snapshot
  fetched from `GET /graph`
- the renderer's force constants are dialed down so the UMAP-seeded
  layout is *settled*, not *rewritten*
- bloom post-processing is enabled for the "luminous" feel
- node click/hover handlers call into `App.tsx` to open the
  `NodePanel` and pulse cluster nodes during `/dream`

## Consequences

**Positive**:

- Most of what we need (3D scene, force simulation, click/hover,
  smooth interaction) ships out of the box. We do not write
  Three.js boilerplate.
- React-friendly API: pass `graphData={...}` and the component
  re-renders correctly on updates.
- Built on Three.js, so when we want a custom shader, particle
  effects, or a starfield background later, we can drop into the
  Three.js scene.
- Active library with examples and a healthy issue tracker.

**Negative / accepted trade-offs**:

- We are dependent on a layered library stack
  (`react-force-graph-3d` → `3d-force-graph` → `three` +
  `d3-force-3d`). Major version bumps in any of those can require
  small adjustments.
- Performance ceiling: at thousands of nodes, the default renderer
  slows down. We mitigate by capping chunks (NFR + the
  `MAX_CHUNKS_IN_DREAMSPACE` setting) and by offering a
  "performance mode" toggle in Phase 5 that disables bloom.
- The library's force simulation is JavaScript, single-threaded.
  At our sizes this is fine; for thousands of nodes we would need
  to seed positions and freeze the simulation after a short tick
  budget.

## Alternatives considered

### Raw Three.js + a hand-rolled force simulation

- *Pros:* full control; we could write GPU-accelerated forces if
  we wanted.
- *Cons:* enormous time investment for the scope of this project.
  Force-directed simulation is a non-trivial physics problem; the
  benefits would not show in the resulting product.

### D3 (2D) force-directed graph

- *Pros:* mature, lightweight, runs at 60 fps on humble laptops.
- *Cons:* 2D. The "galaxy" framing of the product depends on the
  feeling of a navigable, three-dimensional space. A 2D version
  would still be informative but visually flatter — which is the
  exact wrong direction for the goal.

### Sigma.js

- *Pros:* designed for large graphs; 2D-only with WebGL backends.
- *Cons:* same 2D limitation. Used in many production graph apps,
  but not what we want here.

### Cytoscape.js

- *Pros:* powerful styling and layout system; biology-style
  ecosystem.
- *Cons:* 2D-only; styling API is heavy for what we need; the
  visual default is "scientific diagram", not "galaxy".

### react-three-fiber + custom force simulation

- *Pros:* idiomatic React for Three.js; future-proof if the scene
  becomes elaborate.
- *Cons:* we still have to write the force simulation. The
  combination of `react-force-graph-3d` (force) + drop-in Three.js
  customization gives us most of the benefit of r3f at a fraction
  of the code cost. We can refactor to r3f later if Phase 5+
  starts demanding custom rendering.

### Plotly / Bokeh 3D scatter

- *Pros:* trivial to set up.
- *Cons:* not interactive in the way we need (no edge rendering,
  no good click semantics, not embeddable inside a React app
  without friction). Useful for analysis, not for a product.

## When we would revisit

- node count consistently above ~1500 and the simulation can no
  longer keep up (we'd seed positions, freeze after N ticks, or
  consider a WebGPU-based renderer)
- we want richer custom rendering (volumetric clusters, animated
  shaders) and the wrapper API gets in the way (we'd refactor to
  `react-three-fiber`)
- accessibility / performance fallback is needed for users without
  WebGL (we'd add a 2D `cytoscape` view as a graceful degradation
  — already noted as Phase 5 stretch)
