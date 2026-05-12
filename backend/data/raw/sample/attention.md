# Notes on attention as a primitive

Attention rearranges weight. Given a query and a set of keys, the
attention function assigns each key a score, normalizes the scores
into a distribution, and uses that distribution to weight a
corresponding set of values. The output is a *combination* of the
values, not a selection of one.

What makes attention so useful is that the weights are produced from
the input itself. The model does not have to be told in advance which
parts of the input matter; it learns to point at them. Long-range
dependencies that were structurally hard for recurrent networks
become a single softmax away in an attention-based one.

Self-attention takes this one step further: queries, keys, and values
all come from the same sequence. Each token can look at every other
token and decide, on the fly, which neighbors are relevant. The
sequence is no longer a chain but a graph, and the edges are
recomputed at every layer.

The cost is quadratic in sequence length. Most of the engineering
around attention is about avoiding paying that cost in full —
windowed attention, sparse attention, linearized attention, KV
caches at inference time. The primitive is small; the systems built
on top of it are not.
