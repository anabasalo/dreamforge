# Concepts — Phase 1

## What is an embedding?

An **embedding** is a fixed-length list of numbers that represents a
piece of text in a way that captures its *meaning*. Two texts that
say similar things produce vectors that are close together; two texts
about unrelated topics produce vectors that are far apart.

The model dreamforge uses by default, `all-MiniLM-L6-v2`, outputs a
384-dimensional vector for any text up to a few hundred tokens long.
The interesting thing about that vector is what is *not* in it:

- the exact words of the input
- the order of the sentences
- the language's grammar

What it does encode is a compressed representation of *what the text
is about*, in a space where "distance" is meaningful. That is the
single property the rest of the system rests on:

- the **graph** (Phase 2) is built by measuring distance between
  these vectors
- the **clusters** are groups of vectors that live near each other
- the **layout** in 3D is a projection of this space so that humans
  can see the structure

If you only remember one thing from this phase: an embedding turns
"how related are these two passages?" into a number, and that is the
single primitive every other piece of the product builds on.

## Why a vector database?

A vector database stores embeddings alongside the source text and
its metadata, and is optimized for one particular operation:
*given a query vector, find the K vectors closest to it*. That
nearest-neighbor search is the primitive almost every system on top
of embeddings needs.

dreamforge uses ChromaDB in **embedded** mode — meaning it runs
inside the same Python process as FastAPI, and persists to a single
directory on disk (`backend/data/chroma/`). There is no separate
service to install or start. See ADR 0001 for the alternatives that
were considered and why this one fits.

Phase 1 does not actually run a nearest-neighbor query yet — we just
store chunks and read them back in bulk. Phase 2 reads every
embedding back to build the pairwise similarity matrix; Phase 4 will
look up individual chunks by ID for the `/explain` endpoint.

## Why chunk?

We do not embed whole documents because embedding models have a
maximum input length (typically a few hundred tokens), and because
the *unit of similarity* matters. If you embed a whole book, you get
one vector that describes "the book", and similarity to that vector
is roughly "how booky is this query?" — not very useful.

If you split the book into paragraph-sized chunks and embed each,
you can find the *passages* most similar to a query. The unit of
retrieval is now a piece small enough to be useful and large enough
to carry meaning.

## Why *small* chunks in dreamforge?

A typical RAG system uses chunks of ~500 to ~1000 tokens. dreamforge
uses ~256 tokens (about 1024 characters). The reason is that the
output of this phase feeds a *graph*, not a retriever:

- The graph wants many nodes so the topology is interesting (a graph
  of 5 nodes is boring; a graph of 200 nodes can have visible
  clusters and bridges).
- The graph also wants nodes whose meaning is specific enough to
  cluster sharply. A whole-page chunk is "about" many things at once
  and ends up in the middle of many clusters; a small chunk is more
  decisive.

The trade-off is that small chunks lose context (the chunk says
"this is the primary abstraction" but does not say *of what*). For a
RAG pipeline that would matter; for a semantic graph, the embedding
model has already abstracted what each chunk is *about*, and the
context is preserved at the cluster level.

See ADR 0004 for the chunking decision and ADR 0003 for the
embedding-model decision.

## Why overlap?

When you split text on character boundaries, an important sentence
sometimes lands right on the seam between two chunks. If the
beginning of the sentence is in chunk N and the end is in chunk N+1,
neither chunk on its own is a clean unit.

**Overlap** fixes this by making chunk N+1 start a little before
chunk N ends. The same boundary sentence appears in both chunks, so
the embedding of each chunk is computed with the whole sentence in
context, and either chunk is independently meaningful.

The dreamforge default is 120 characters of overlap on top of 1024
characters of content, about a 12 % overhead. The splitter also
prefers paragraph, then sentence, then newline boundaries within a
small window of the target size, so the actual seam usually lands
somewhere natural and the overlap is rarely needed in the worst-case
way.

## Why metadata?

Every chunk we store carries six pieces of metadata:

- `doc_id` — a stable UUID for the version of the document this
  chunk came from
- `doc_name` — the original filename, e.g. `kafka.md`
- `chunk_index` — the 0-based position of this chunk in the doc
- `source_type` — `pdf` / `markdown` / `text`
- `uploaded_at` — ISO-8601 timestamp of the ingestion
- `char_count` — length of the chunk text

Metadata is what lets us do interesting things without a separate
database:

- *re-uploads are idempotent*: we delete every chunk where
  `doc_name == X` before inserting the new version (a single Chroma
  `where` filter)
- *the side panel* in Phase 3 will show the doc name and chunk
  position of whatever node the user clicks on
- *the graph engine* in Phase 2 will use `chunk_index` ordering when
  computing intra-document edges

The full schema, including which fields are required and why
ChromaDB's metadata constraints shape the design, is in
[`docs/00-design/04-data-model.md`](../00-design/04-data-model.md).

## Why the chunk cap?

The dreamspace is capped at 800 chunks by default
(`MAX_CHUNKS_IN_DREAMSPACE`). Three reasons:

1. **3D rendering performance.** `react-force-graph-3d` with bloom
   stays at 60 fps comfortably up to ~500 nodes on a typical laptop;
   above ~1000 it drops noticeably. The cap is set so the worst
   case is still smooth.
2. **LLM cost.** Phase 2 will call the LLM once per cluster for
   theme labels, and Phase 4 will call it for `/dream` and
   `/explain`. The number of clusters scales loosely with the number
   of chunks; the cap bounds the worst case.
3. **Demo coherence.** A "galaxy" of 5000 fuzzy nodes is harder to
   read than a galaxy of 300 deliberate ones. The cap nudges the
   user toward focused, interesting document sets.

The cap is enforced **transactionally**: an upload that would push
the dreamspace over the cap is rejected entirely, with no partial
state. This is why `ingest_batch` parses and chunks every file
first, *then* checks the total, *then* writes.

## Why a `Protocol` for the embedder and the LLM?

Two of the most opinionated dependencies in this project are the
embedding model and the LLM provider. Both could easily be replaced
later (a bigger embedder for better clusters; OpenAI for richer
dreams). The code that uses them depends only on a tiny `Protocol`:

```python
class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

class LLMClient(Protocol):
    @property
    def model_name(self) -> str: ...
    def chat(self, *, system: str, user: str,
             temperature: float = 0.7, max_tokens: int = 512) -> str: ...
```

The real implementations (`SentenceTransformerEmbedder`, `GroqClient`)
live in their own modules and are wired in at the FastAPI dependency
layer. Tests inject a `FakeEmbedder` and a `FakeLLMClient` instead.
The business logic never knows which one it has.

This is what makes the entire test suite run offline in seconds.
