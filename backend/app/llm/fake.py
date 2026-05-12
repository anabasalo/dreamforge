"""Deterministic in-memory ``LLMClient`` used by tests.

The fake never calls the network and never imports the ``groq`` SDK.
It records calls so a test can assert that the prompt is shaped
correctly, and it returns a deterministic string keyed off ``(system,
user)`` so assertions stay stable across runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class _Call:
    system: str
    user: str
    temperature: float
    max_tokens: int


@dataclass
class FakeLLMClient:
    """A reproducible fake."""

    answer: str | None = None
    calls: list[_Call] = field(default_factory=list)
    model: str = "fake-llm"

    @property
    def model_name(self) -> str:
        return self.model

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        self.calls.append(
            _Call(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        if self.answer is not None:
            return self.answer
        digest = hashlib.sha256(f"{system}::{user}".encode()).hexdigest()[:6]
        return f"fake-response-{digest}"

    @property
    def last_call(self) -> _Call | None:
        return self.calls[-1] if self.calls else None
