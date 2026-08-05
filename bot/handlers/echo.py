from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.models import User
from bot.localization.en import MESSAGES
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="echo")


@router.message(Command("profile"))
@router.message(F.text == "👤 Profile")
async def cmd_profile(message: Message, db_user: User) -> None:
    try:
        text = MESSAGES["profile"].format(
            telegram_id=db_user.telegram_id,
            username=db_user.username or "—",
            full_name=db_user.full_name or "—",
            is_admin="Yes" if db_user.is_admin else "No",
            created_at=db_user.created_at.strftime("%Y-%m-%d %H:%M UTC") if db_user.created_at else "—",
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /profile handler: %s", exc)
        await message.answer("An unexpected error occurred. Please try again later.")


@router.message(F.text & ~F.text.startswith("/"))
async def echo_handler(message: Message) -> None:
    try:
        if not message.text:
            return
        text = MESSAGES["echo"].format(text=message.text)
        await message.answer(text)
    except Exception as exc:
        logger.exception("Error in echo handler: %s", exc)
        await message.answer("An unexpected error occurred. Please try again later.")
