from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.models import User
from bot.localization import MESSAGES
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="echo")

MAX_ECHO_LENGTH = 1000


@router.message(Command("profile"))
@router.message(F.text == "👤 ملفي")
@router.message(F.text == "👤 Profile")
async def cmd_profile(message: Message, db_user: User) -> None:
    try:
        username_display = f"@{db_user.username}" if db_user.username else "—"
        text = MESSAGES["profile"].format(
            telegram_id=db_user.telegram_id,
            username=username_display,
            full_name=db_user.full_name or "—",
            is_admin="نعم" if db_user.is_admin else "لا",
            created_at=db_user.created_at.strftime("%Y-%m-%d %H:%M UTC") if db_user.created_at else "—",
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /profile handler: %s", type(exc).__name__)
        await message.answer(MESSAGES.get("error", "حدث خطأ غير متوقع."))


@router.message(F.text & ~F.text.startswith("/"))
async def echo_handler(message: Message) -> None:
    try:
        if not message.text:
            return

        cleaned = message.text.strip()
        if not cleaned:
            return

        if len(cleaned) > MAX_ECHO_LENGTH:
            cleaned = cleaned[:MAX_ECHO_LENGTH] + "…"

        text = MESSAGES["echo"].format(text=cleaned)
        await message.answer(text)
    except Exception as exc:
        logger.exception("Error in echo handler: %s", type(exc).__name__)
        await message.answer(MESSAGES.get("error", "حدث خطأ غير متوقع."))
