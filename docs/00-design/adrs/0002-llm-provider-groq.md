# ADR 0002 — Use Groq behind an `LLMClient` Protocol

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

The system uses an LLM in three places:

1. **Theme labeling** during graph build (one short call per
   non-noise cluster, in parallel)
2. **Dream generation** (`POST /dream`) — one larger call producing
   a multi-paragraph narrative
3. **Relationship explanation** (`POST /explain`) — one short call
   producing a paragraph

Requirements relevant to this decision:

- runs at zero monetary cost on a free tier (NFR-4)
- low latency: theme labels and `/explain` should not feel slow,
  and `/dream` should respond in under five seconds (NFR-1.3)
- accessible from a developer laptop without a GPU
- swappable for a different provider later, without rewriting `core/`

## Decision

Use **Groq** as the default LLM provider, with the model
`llama-3.1-8b-instant`, accessed through the official `groq`
Python SDK.

All access goes through an `LLMClient` Protocol:

```python
class LLMClient(Protocol):
    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str: ...
```

The Groq implementation lives in `backend/app/llm/groq_client.py`.
A deterministic `FakeLLMClient` in `backend/app/llm/fake.py` is
used in tests. Modules in `core/` accept an `LLMClient` and never
import the `groq` SDK directly.

## Consequences

**Positive**:

- Free tier with generous limits at the time of writing; no card
  required.
- Very fast inference (Groq's calling card) — theme labels return
  in well under a second, which keeps the upload pipeline snappy.
- The Protocol lets us run all tests without network access or API
  keys.
- Switching providers later is a one-file change
  (`backend/app/llm/<new>_client.py` plus the `LLM_PROVIDER`
  setting).

**Negative / accepted trade-offs**:

- Single point of failure: when Groq is down or rate-limits us, the
  product is degraded. We mitigate by failing theme labels softly
  (fall back to `Cluster N`) and by retrying `/dream` and
  `/explain` once before returning `502 LLMUnavailable`.
- Free-tier quality is bounded by what Groq offers. Llama-3.1-8b is
  good enough for theme labeling and grounded narrative, but not as
  fluent as larger paid models for the most surreal `/dream` mode.
- The free tier may change. The Protocol is the insurance against
  this; in the worst case we point at OpenAI or a local Ollama
  instance.

## Alternatives considered

### OpenAI (`gpt-4o-mini` or similar)

- *Pros:* highest narrative quality, mature SDK, well-documented.
- *Cons:* paid (per-token), conflicts with NFR-4. Could be the
  natural drop-in if a future user wants better dreams; the
  Protocol supports this.

### Anthropic (`claude-3.5-haiku` or similar)

- *Pros:* high quality, good at "interpretive" prompts.
- *Cons:* paid, no free-tier access for repeated demos.

### Local Ollama (e.g. `llama3:8b` or `mistral`)

- *Pros:* completely free, no network, no rate limits.
- *Cons:* requires the user to install Ollama and pull a model
  (~5 GB), which conflicts with NFR-5 ("a single
  `docker compose up` brings up a working service from a fresh
  clone"). On laptops without a GPU, latency is poor for the
  longer `/dream` calls.

### `transformers` directly inside the FastAPI process

- *Pros:* no external service.
- *Cons:* heavy: the Docker image grows by gigabytes; first
  request is very slow without a model warmer; and quality at
  sub-7B sizes (what fits on a laptop) is worse than what Groq
  offers for free.

### A multi-provider router (e.g. `litellm`)

- *Pros:* one client, many providers.
- *Cons:* extra dependency for a project that only needs one
  provider at a time. Our `LLMClient` Protocol is a 10-line
  interface; we do not need a router for it.

## When we would revisit

- Groq's free tier becomes too restrictive (rate limits start
  hurting the demo)
- a user asks for higher-quality dreams and is willing to pay
  (we add an OpenAI client side-by-side)
- the project gains an offline / self-hosted requirement (we add
  an Ollama client and document the trade-off)
