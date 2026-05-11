# ADR 0007 — One global dreamspace, no collections, no users

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

The system stores documents and their derived graph somewhere. The
question is *how that storage is partitioned*: by user, by named
"workspace", or not at all?

Reasonable shapes considered:

1. **Single global dreamspace** — there is exactly one active graph
   at a time. New uploads extend it; `POST /reset` clears it.
2. **Named dreamspaces** — like rag-systems collections; the user
   names their dreamspace and can switch between them.
3. **Anonymous session-id dreamspaces** — every browser session gets
   its own ephemeral graph (cookie or local-storage scoped).
4. **Authenticated multi-user** — accounts, isolation, sharing.

The product has one core interaction (drop documents → watch the
galaxy form → press Dream). Anything that competes with that
interaction for attention — a collection picker, a sign-in screen,
a "create new dreamspace" wizard — directly weakens it.

## Decision

The system holds **exactly one global dreamspace at a time**.

- ChromaDB has one collection, hardcoded as `dreamforge`.
- The graph snapshot is one file at
  `backend/data/graphs/current.json` and one in-memory variable.
- There is no "select dreamspace" UI.
- `POST /reset` clears it. This is the only way to start over.
- The frontend has no notion of identity; it talks to a single
  backend that holds a single graph.

## Consequences

**Positive**:

- The first-time experience is unambiguous: one upload zone, one
  big button. Nothing else.
- The API surface stays small: `/upload`, `/graph`, `/dream`,
  `/explain`, `/chunks/{id}`, `/reset`, `/health`. No collection
  CRUD.
- The data model stays small: no `User`, no `Workspace`, no
  ownership rules.
- Tests are simpler: no fixtures setting up "the right
  collection".

**Negative / accepted trade-offs**:

- Two people sharing a deployment will overwrite each other's
  dreamspace. The system is honest about this (it is a single-user
  product), but a careless deployment could surprise users.
- A user who wants to keep two distinct experiments around at the
  same time has to either save snapshots manually (copy
  `current.json`) or wait for a future iteration.
- The choice is intentionally *less impressive on paper* (no
  multi-tenancy, no sharing, no auth) than a collection-based
  system. The trade is in favor of demo coherence and scope
  discipline.

## Alternatives considered

### Named dreamspaces (collections, like rag-systems)

- *Pros:* lets users keep multiple experiments; mirrors familiar
  patterns; easy to extend later.
- *Cons:* introduces UI surface (picker, naming) that competes
  with the core interaction. The product's promise is "watch
  *these* documents dream", not "manage your dream library".

### Session-id dreamspaces

- *Pros:* private per-browser; no need for explicit auth; demo
  visitors could each get their own galaxy without trampling each
  other.
- *Cons:* session-bound state is invisible; "where did my
  dreamspace go?" is a real footgun. Backend complexity grows
  (per-session Chroma collections, per-session caches). Not worth
  it for the targeted scope.

### Authenticated multi-user

- *Pros:* the "real product" answer.
- *Cons:* doubles the surface area of the project (auth, accounts,
  password reset, ownership) for no demo benefit. Out of scope by
  the requirements doc explicitly.

## When we would revisit

- the product gains a second user beyond its author (we add
  per-session dreamspaces with a clear UI for switching)
- we want a "save this dreamspace" feature (we add named
  dreamspaces as a thin layer on top — store snapshots by name,
  let the user list and load them)
- we need access controls (we layer auth on top of named
  dreamspaces — at that point the product has changed character
  and a new ADR supersedes this one)
