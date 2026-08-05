from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.localization import MESSAGES
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="help")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    try:
        await message.answer(MESSAGES["help"], parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /help: %s", type(exc).__name__)
        await message.answer(MESSAGES.get("error", "حدث خطأ."))
