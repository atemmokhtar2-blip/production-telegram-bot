from __future__ import annotations

from collections.abc import Awaitable, Callable

from bot.services.ai_service import AIService
from bot.utils.logger import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[str, int, int], Awaitable[None]]

# Single focused design pass — fast enough for interactive use
_SYSTEM = (
    "أنت مهندس بوتات تيليجرام خبير (aiogram 3 / Python). "
    "من وصف المستخدم، أنشئ وثيقة تصميم جاهزة للتنفيذ بالعربية تشمل:\n"
    "1) ملخص الفكرة والجمهور\n"
    "2) الأوامر والأزرار\n"
    "3) هيكل الملفات المقترح\n"
    "4) نموذج البيانات إن لزم\n"
    "5) صلاحيات المشرف والأمان\n"
    "6) متغيرات .env\n"
    "7) خطوات التشغيل السريعة\n"
    "كن واضحاً ومختصراً بدون حشو."
)


class AgentPipeline:
    """Fast single-pass bot designer (replaces the slow 11-agent chain)."""

    def __init__(self, ai: AIService | None = None) -> None:
        self._ai = ai or AIService()

    @property
    def agent_count(self) -> int:
        return 1

    async def run(
        self,
        user_description: str,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> str:
        if on_progress:
            await on_progress("تصميم البوت", 1, 1)

        desc = user_description.strip()
        try:
            result = await self._ai.chat(
                [
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": f"وصف المستخدم:\n{desc}\n\nصمّم البوت الآن.",
                    },
                ],
                temperature=0.45,
            )
        except Exception as exc:
            logger.exception("Design pass failed: %s", type(exc).__name__)
            result = f"[تعذّر التصميم: {type(exc).__name__}]"

        header = (
            "🚀 <b>تصميم البوت</b>\n"
            f"<i>{desc[:180]}{'…' if len(desc) > 180 else ''}</i>\n\n"
        )
        return header + (result or "").strip()
