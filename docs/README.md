# dreamforge — A Hands-On Course on Semantic-Graph Products

This folder is a self-paced course built into the project. It mirrors the
implementation phases of `dreamforge` and explains both *what* the system does
and *why* each design decision was made.

`dreamforge` is a small, focused product with one magical interaction:

> Upload documents, watch the AI transform them into an explorable 3D
> "semantic galaxy" of clusters, themes, and hidden relationships, and
> press one button to read the AI's *Dream* — a grounded but evocative
> narrative woven from the document set.

If you have never built a system that mixes embeddings, clustering, graph
visualization, and LLM-as-interpreter, start with Phase 0 and walk
through each phase in order. Every phase ships:

- working code under `backend/` and `frontend/` (with backend tests under `backend/tests/`)
- a course folder under `docs/0X-*/` with concepts, walkthroughs,
  alternatives, and references

## What you will learn

By the end of the course you will be able to:

- explain how an embedding model turns text into a vector and why those
  vectors form usable "semantic space"
- build a sparse k-NN graph on top of dense embeddings and explain why
  sparsification matters
- choose between density-based and centroid-based clustering and
  justify the trade-offs
- use UMAP to seed a 3D layout that a force-directed renderer can take
  the rest of the way
- render a real-time, interactive 3D graph in the browser with
  React + Three.js (via `react-force-graph-3d`)
- design prompts that ask an LLM to *interpret* a document set, not
  just summarize it, and expose creativity as a temperature dial
- ship the whole thing as a two-service app behind `docker compose up`

## Prerequisites

- comfort with Python 3.11+ and TypeScript / modern React
- basic understanding of HTTP and JSON
- a terminal, `git`, and Docker (Docker only required from Phase 5)
- a free Groq API key (for the LLM call). Sign up at
  [console.groq.com](https://console.groq.com)

You do **not** need a GPU. Embeddings, UMAP, and HDBSCAN run on CPU and
are fast enough on a typical laptop for hundreds of chunks.

## Learning path

| Phase | Folder | Topic | Time |
| --- | --- | --- | --- |
| 0 | [`00-design/`](00-design/) | Vision, requirements, architecture, ADRs | ~3 h |
| 1 | [`01-ingestion/`](01-ingestion/) | Parsing, chunking, embeddings, vector stores | ~6 h |
| 2 | [`02-semantic-graph/`](02-semantic-graph/) | Similarity, k-NN graphs, HDBSCAN, UMAP, theme labels | ~8 h |
| 3 | [`03-visualization/`](03-visualization/) | React + Three.js, force-directed 3D rendering, click-to-explore | ~8 h |
| 4 | [`04-dream-generation/`](04-dream-generation/) | LLM-as-interpreter, temperature, grounded creativity, relationship explanation | ~6 h |
| 5 | [`05-deployment/`](05-deployment/) | Multi-stage Docker, two-service compose, CI | ~4 h |

The source of truth for what is implemented is the code in `backend/` /
`frontend/` and the tests in `backend/tests/`.

## How each phase doc is organized

Every phase folder follows the same shape so you always know where to look:

- `README.md` — learning goals, what was built, walkthrough, exercises
- `concepts.md` — the theory behind the phase
- `alternatives.md` — what else we could have used and why we did not
- `references.md` — papers, official docs, and recommended reading

## Glossary

A short reference for common terms is in
[`00-design/glossary.md`](00-design/glossary.md).

## Conventions

- Code blocks are runnable unless explicitly marked otherwise.
- File paths are relative to the repository root (the parent of `docs/`).
- ADRs (Architecture Decision Records) live under
  [`00-design/adrs/`](00-design/adrs/) and follow a Context / Decision /
  Consequences / Alternatives format.
- Backend code is Python (FastAPI, ChromaDB, sentence-transformers,
  scikit-learn, HDBSCAN, UMAP, Groq).
- Frontend code is TypeScript (React, Vite, `react-force-graph-3d`,
  Tailwind).
