from __future__ import annotations

import os
from typing import Any

from bot.utils.logger import get_logger
from config import get_settings

logger = get_logger(__name__)


class AIService:
    """Chat via optional API keys (OpenAI/Groq/OpenRouter), then g4f."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model = getattr(self._settings, "ai_model", None) or "gpt-4o-mini"

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
    ) -> str:
        model = model or self._model
        errors: list[str] = []

        for name, base, key_env, default_model in (
            ("openai", "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"),
            ("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
            ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "openai/gpt-4o-mini"),
        ):
            key = os.getenv(key_env, "").strip()
            if not key:
                continue
            try:
                text = await self._openai_compatible(
                    base_url=base,
                    api_key=key,
                    model=os.getenv("AI_MODEL", default_model),
                    messages=messages,
                    temperature=temperature,
                )
                if text:
                    return text
            except Exception as exc:
                errors.append(f"{name}:{type(exc).__name__}")
                logger.warning("provider %s failed: %s", name, type(exc).__name__)

        try:
            text = await self._g4f(messages, model=model, temperature=temperature)
            if text:
                return text
        except Exception as exc:
            errors.append(f"g4f:{type(exc).__name__}")
            logger.warning("g4f failed: %s", type(exc).__name__)

        raise RuntimeError(
            "All AI providers failed: " + (", ".join(errors) if errors else "none")
        )

    async def _openai_compatible(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> str:
        import aiohttp

        url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=90)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise RuntimeError(str(data)[:200])
                return (data["choices"][0]["message"]["content"] or "").strip()

    async def _g4f(self, messages: list[dict[str, str]], *, model: str, temperature: float) -> str:
        from g4f.client import AsyncClient

        client = AsyncClient()
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages)
