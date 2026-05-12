"""Custom exceptions raised by ``app.core.*``.

Layers below ``api/`` MUST NOT raise FastAPI's ``HTTPException`` directly.
The API layer catches these in ``app/main.py`` and maps them to HTTP
status codes per the contract in ``docs/00-design/05-api-contract.md``.

The class names mirror the public ``error`` codes in the JSON error
envelope, so they are deliberately *not* suffixed with ``Error``.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Raised when a document cannot be parsed or chunked."""


class ChunkLimitExceeded(Exception):
    """Raised when an upload would push the dreamspace past its chunk cap."""

    def __init__(self, current: int, incoming: int, limit: int) -> None:
        self.current = current
        self.incoming = incoming
        self.limit = limit
        super().__init__(
            f"Upload would push the dreamspace from {current} to "
            f"{current + incoming} chunks, which exceeds the cap of {limit}."
        )


class EmptyDreamspace(Exception):
    """Raised when an operation requires chunks but the dreamspace is empty."""


class EntityNotFound(Exception):
    """Raised when a chunk or cluster id is not in the current snapshot."""

    def __init__(self, entity: str) -> None:
        self.entity = entity
        super().__init__(f"Entity '{entity}' is not in the current snapshot.")


class LLMUnavailable(Exception):
    """Raised when the LLM provider returns an error or is misconfigured."""
