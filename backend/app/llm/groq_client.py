"""Groq implementation of the ``LLMClient`` Protocol.

The ``groq`` SDK is imported lazily inside ``chat`` so importing this
module does not require a key or a network round-trip. Tests use
``app.llm.fake.FakeLLMClient`` instead.

See ADR 0002 for the choice of Groq.
"""

from __future__ import annotations

from app.core.exceptions import LLMUnavailable


class GroqClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise LLMUnavailable(
                "GROQ_API_KEY is not configured. "
                "Set it in .env or the environment to use the Groq LLM."
            )
        try:
            from groq import Groq
        except ImportError as exc:
            raise LLMUnavailable(
                "groq package is not installed. "
                "Install via `pip install groq`."
            ) from exc
        self._client = Groq(api_key=self._api_key)
        return self._client

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        client = self._ensure_client()
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailable(f"Groq chat completion failed: {exc}") from exc

        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message is None or choice.message.content is None:
            raise LLMUnavailable("Groq returned an empty completion.")
        return choice.message.content.strip()
