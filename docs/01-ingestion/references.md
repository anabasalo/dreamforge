# References — Phase 1

Things to read if you want to dig deeper into the concepts this phase
touches. Each link has a one-line "why read this".

## Embeddings

- [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://arxiv.org/abs/1908.10084)
  — *the* paper behind `sentence-transformers`. Explains why
  fine-tuning BERT with a siamese objective produces vectors where
  cosine similarity is meaningful, which is the property the rest of
  dreamforge depends on.
- [Sentence-Transformers documentation](https://www.sbert.net/) —
  the up-to-date user-facing docs, including the model zoo and
  benchmark tables. Worth a 10-minute skim before you swap the
  default model.
- [MTEB: Massive Text Embedding Benchmark](https://huggingface.co/spaces/mteb/leaderboard)
  — a leaderboard for embedding models across retrieval, clustering,
  classification, and more. Useful when you are deciding whether a
  bigger embedder is worth the latency.
- [Hugging Face hub page for `all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
  — the model dreamforge ships with. The model card explains its
  training data, intended use, and known limits.

## Vector databases

- [ChromaDB documentation](https://docs.trychroma.com/) — the
  official docs. Focus on the persistent-client mode (what
  dreamforge uses) and the `where`-filter semantics.
- [Pinecone: hybrid search blog post](https://www.pinecone.io/learn/hybrid-search-intro/)
  — even though we do not use Pinecone, this is a clear writeup of
  what a vector index actually does at query time and how it
  combines with metadata filters.
- [FAISS: A Library for Efficient Similarity Search](https://github.com/facebookresearch/faiss/wiki)
  — Facebook's library; reading the wiki is the easiest way to
  understand HNSW, IVF, and the index families ChromaDB hides behind
  its API.

## Chunking

- [LangChain text splitters guide](https://python.langchain.com/docs/how_to/recursive_text_splitter/)
  — a survey of text-splitter strategies (recursive, character,
  token, semantic). Useful even if you do not use LangChain.
- ["Chunking Strategies for LLM Applications" — Pinecone blog](https://www.pinecone.io/learn/chunking-strategies/)
  — a practitioner-level discussion of how chunk size affects
  retrieval and downstream task quality.
- ["Lost in the Middle: How Language Models Use Long Contexts"](https://arxiv.org/abs/2307.03172)
  — Liu et al., 2023. Why dumping the whole document into the LLM
  is not a substitute for retrieval: models attend disproportionately
  to the beginning and end of long contexts.

## FastAPI patterns

- [FastAPI: dependencies docs](https://fastapi.tiangolo.com/tutorial/dependencies/)
  — the dependency-injection model dreamforge uses for the embedder
  and vector store.
- [FastAPI: testing docs](https://fastapi.tiangolo.com/tutorial/testing/)
  and [dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
  — how `tests/conftest.py::client` swaps real deps for fakes.
- [Pydantic Settings docs](https://docs.pydantic.dev/latest/usage/pydantic_settings/)
  — the basis for `app/config.py`.

## Python testing

- [pytest fixtures docs](https://docs.pytest.org/en/stable/explanation/fixtures.html)
  — the model behind our `conftest.py` (factories, tmp_path,
  scope).
- ["Test doubles" — Martin Fowler](https://martinfowler.com/bliki/TestDouble.html)
  — the canonical taxonomy (dummy, fake, stub, mock, spy). We use
  *fakes* (a deterministic embedder, a recording LLM) rather than
  mocks; this article explains the difference.

## Background reading on the broader idea

- ["Building an AI-Powered Semantic Memory System with Graph
  Databases and Vector Embeddings"](https://nikhil-datasolutions.medium.com/building-an-ai-powered-semantic-memory-system-with-graph-databases-and-vector-embeddings-adba193f916d)
  — adjacent in spirit to dreamforge: starts from documents +
  embeddings and builds a structure on top, although it goes in a
  different (graph-database) direction.
- ["The Semantic Knowledge Graph"](https://arxiv.org/abs/1609.00464)
  — older work on automatically generated semantic graphs. Useful
  context for how to think about edges and traversal.
