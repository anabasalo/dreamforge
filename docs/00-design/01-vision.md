# Vision

## Problem statement

Most products built on top of large language models reduce to "ask a
question, get a paragraph back". That pattern is useful, but it
collapses the model's capabilities into a single, linear interaction
that hides the underlying structure of the user's data. When a person
has fifty notes, three articles, and two PDFs, what they often want is
not an answer; it is *to see how those documents relate to each other*
— which ideas cluster, which themes recur, which connections were
hiding in plain sight.

`dreamforge` is a small, focused application built around a single,
non-conversational interaction with an LLM-powered system: the user
uploads a set of documents and watches them rearrange themselves into
an explorable, three-dimensional "semantic galaxy" of clustered
chunks, with AI-generated theme labels and an on-demand "Dream"
narrative that interprets the document set as a whole.

The point is to make the latent structure of a document collection
*visible* and *navigable*, and to use the LLM as an interpreter of
that structure rather than as a question-answering oracle.

## Target reader and use case

The intended reader is an engineer who wants to understand how
embeddings, graph algorithms, dimensionality reduction, and large
language models combine into a single interactive product, and to
have a working reference implementation they can extend.

The end-user surface is a single page that accepts a few documents
(notes, articles, papers, fragments) and produces a navigable graph.
Typical usage:

- "I have a folder of conference notes — what themes did I write
  about most this year?"
- "I dropped in three papers on distributed systems and a Borges
  story — does the system find a real connection or just a forced
  one?"
- "I want to see whether two of my own essays are saying related
  things without me having to re-read them."

`dreamforge` is not a knowledge base, an assistant, or a search
engine. It does not answer factual questions. It produces an
*interpretation* of a document set.

## Success criteria

The project is successful when all of the following are true:

1. A user can drop one or more PDF, Markdown, or text files into the
   browser and, within a few seconds, see a three-dimensional graph
   of chunks, colored and grouped by cluster, with a short
   AI-generated theme label per cluster.
2. Clicking any node opens a side panel showing the underlying chunk
   text, its source filename, and its top semantic neighbors.
3. Pressing the **Dream** button produces an LLM-generated narrative
   that references the cluster themes by name, weaving them into a
   short, evocative reading of the document set as a whole.
4. A **temperature** control changes the character of the dream from
   factual synthesis (low) to surreal interpretation (high) on the
   same document set, demonstrating that the slider is a real dial
   and not a label.
5. Asking the system to **explain** the connection between any two
   nodes (or any two clusters) returns a short, grounded paragraph
   that names concrete reasons for the connection.
6. The whole system runs from a clean clone with `docker compose up`
   and a populated `.env`, requiring no paid services.
7. A reader can follow `docs/` from Phase 0 to Phase 5 and understand
   every decision the project makes.

## Non-goals

Explicitly out of scope:

- **Authentication and multi-tenancy.** There are no user accounts.
  Anyone with network access to the running service can upload to
  and reset the same single dreamspace.
- **Multiple coexisting dreamspaces.** The system holds exactly one
  active graph at a time. `POST /reset` clears it.
- **Question answering / RAG chat.** The LLM is used for theme
  labeling, dream narration, and relationship explanation. It is not
  exposed as a chatbot, and there is no `/query` endpoint.
- **Real-time collaboration.** The graph is single-user from a
  product perspective; concurrent uploads from different browsers
  share the same dreamspace and overwrite each other's view.
- **Long-term persistence.** The vector store and graph cache live
  in mounted volumes for the convenience of demos, but the system
  has no backup, versioning, or migration story.
- **Large corpora.** The system targets dozens to a few hundred
  chunks. There is a hard cap on chunks per upload to keep the
  visualization responsive.
- **Fine-tuning or training.** Embedding and generation models are
  used as-is.

## Demo narrative (the 90-second walkthrough)

The intended walkthrough of a finished system, used to drive the design:

1. *Setup.* `docker compose up`. The frontend is reachable at
   `localhost:5173`; the backend at `localhost:8000`. The dreamspace
   is empty and the page shows a single prompt: "Drop documents
   anywhere to begin."
2. *Upload.* The user drags four files into the page: a Kafka design
   excerpt, the abstract of a transformer paper, a public-domain
   passage on memory, and a short notes file. The upload zone shows
   chunk counts as each file is processed.
3. *Galaxy emerges.* Within a few seconds, a three-dimensional graph
   of nodes appears, animated into place. Nodes are colored by
   cluster. A bottom-left legend shows cluster theme labels:
   *Persistence*, *Attention*, *Memory*, *Time*. Edges between nodes
   indicate semantic similarity above a threshold.
4. *Explore.* The user clicks a node in the *Persistence* cluster.
   A side panel slides in with the chunk text ("Kafka treats the log
   as the primary abstraction…"), its source filename, and a list of
   its top semantic neighbors — including one in the *Memory*
   cluster. Clicking that neighbor calls `/explain` and shows a short
   paragraph naming why the two passages are related.
5. *Dream.* The user moves the temperature slider near the middle and
   presses **Dream**. The graph slowly pulses while the model thinks.
   A narrative panel types in: "Across these documents, an idea of
   *persistence* keeps surfacing — sometimes as a log on disk,
   sometimes as a layer of attention, sometimes as a corridor of
   library shelves…". As cluster names appear in the narrative, the
   corresponding nodes pulse in the 3D scene.
6. *Reset.* The user clicks **Reset**, the graph fades, and the page
   returns to the empty prompt, ready for the next set of documents.

This narrative is the contract the rest of the design has to satisfy.
