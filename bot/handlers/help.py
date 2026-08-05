from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.localization.en import MESSAGES
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="help")


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Help")
async def cmd_help(message: Message) -> None:
    try:
        await message.answer(MESSAGES["help"], parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /help handler: %s", exc)
        await message.answer("An unexpected error occurred. Please try again later.")
