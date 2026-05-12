"""LLM client Protocol.

Every call to a Large Language Model in this project goes through this
interface. Phase 2 adds theme labeling on top of it, Phase 4 adds
``/dream`` and ``/explain``.

The contract is intentionally a single ``chat`` method that takes a
``system`` message, a ``user`` message, and returns a string. We
deliberately do *not* expose streaming, function calling, or
provider-specific knobs — those would leak into ``core/`` and break
the provider-agnostic story (see ADR 0002).
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Anything that can produce a chat completion."""

    @property
    def model_name(self) -> str: ...

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str: ...
