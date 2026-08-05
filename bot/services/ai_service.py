from __future__ import annotations

from typing import Any

from g4f.client import AsyncClient

from bot.utils.logger import get_logger
from config import get_settings

logger = get_logger(__name__)


class AIService:
    """Async wrapper around g4f for agent / bot-generation workloads.

    Uses free GPT4Free providers — no API key required by default.
    Suitable for generating bot logic, prompts, and agent replies.
    """

    def __init__(self) -> None:
        self._client = AsyncClient()
        self._settings = get_settings()
        self._model = getattr(self._settings, "ai_model", None) or "gpt-4o-mini"

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat completion request and return the assistant text."""
        try:
            response = await self._client.chat.completions.create(
                model=model or self._model,
                messages=messages,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            return (content or "").strip()
        except Exception as exc:
            logger.exception("AIService.chat failed: %s", type(exc).__name__)
            raise

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Single-turn completion helper."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages)

    async def generate_bot_spec(self, user_request: str) -> str:
        """Generate a structured bot specification from a natural-language request."""
        system = (
            "You are an expert Telegram bot architect. "
            "Given a user request, produce a clear structured specification covering: "
            "purpose, commands, handlers, data models, admin features, and AI agent roles. "
            "Respond in the same language as the user request."
        )
        return await self.complete(user_request, system=system)
