# Notes on Kafka and the log abstraction

Kafka treats the log as the primary abstraction. A log is an
append-only, totally ordered sequence of records, and almost every
useful property of the system follows from this single idea. Producers
write to the end of the log; consumers read from positions they
maintain themselves. Retention is decoupled from delivery, so the same
record can be replayed by a new consumer years after it was written.

Because the log is durable and ordered, downstream services can be
rebuilt from scratch by replaying it. Materialized views, search
indexes, and feature stores all become "subscribers of a log",
periodically catching up to the head. The system's memory of what
happened is not a database row but a position in a log.

Partitioning is what lets a single conceptual log scale across
machines. Each partition is an independent log; consumers coordinate
which partitions they own via the broker. Order is preserved within a
partition but not across them, and that constraint pushes data
modeling decisions all the way up to the producer.

Compaction lets the log behave like a key-value store while still
being a log. The latest record for a given key survives; older records
for the same key are eventually garbage collected. The log is no
longer a complete history, but it is still a faithful snapshot of the
present.
