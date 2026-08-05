from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from bot.agents.prompts import AGENTS
from bot.services.ai_service import AIService
from bot.utils.logger import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[str, int, int], Awaitable[None]]


class AgentPipeline:
    """Runs the 11-agent pipeline to design a Telegram bot from a description."""

    def __init__(self, ai: AIService | None = None) -> None:
        self._ai = ai or AIService()
        self._agents = AGENTS

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    async def run(
        self,
        user_description: str,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> str:
        context_parts: list[str] = [f"طلب المستخدم:\n{user_description.strip()}"]

        for index, agent in enumerate(self._agents, start=1):
            name = agent["name"]
            if on_progress:
                await on_progress(name, index, self.agent_count)

            prior = "\n\n---\n\n".join(context_parts[-4:])  # keep last chunks for context size
            user_msg = (
                f"المرحلة {index}/{self.agent_count} — {name}\n\n"
                f"السياق السابق:\n{prior}\n\n"
                f"نفّذ مهمتك الآن بوضوح."
            )
            try:
                result = await self._ai.chat(
                    [
                        {"role": "system", "content": agent["system"]},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.5,
                )
            except Exception as exc:
                logger.exception("Agent %s failed: %s", agent["id"], type(exc).__name__)
                result = f"[تعذّر إكمال وكيل {name}: {type(exc).__name__}]"

            context_parts.append(f"### {name}\n{result}")
            logger.info("Agent finished %s (%s/%s)", name, index, self.agent_count)

        # Final document is the orchestrator output (last), with a short header
        final = context_parts[-1]
        header = (
            "🚀 <b>نتيجة 11 وكيل — تصميم البوت</b>\n"
            f"<i>الوصف:</i> {user_description[:200]}{'…' if len(user_description) > 200 else ''}\n\n"
        )
        # strip markdown header from orchestrator if present for cleaner send
        body = final.replace("### Orchestrator\n", "").replace("### Orchestrator", "")
        return header + body
