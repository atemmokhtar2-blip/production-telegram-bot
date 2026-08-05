from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.database.models import User
from bot.keyboards.reply import main_menu_keyboard
from bot.localization import MESSAGES
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User) -> None:
    try:
        name = message.from_user.full_name if message.from_user else "مستخدم"
        text = MESSAGES["start"].format(name=name)
        await message.answer(text, reply_markup=main_menu_keyboard())
        logger.info("User telegram_id=%s started the bot", db_user.telegram_id)
    except Exception as exc:
        logger.exception("Error in /start handler: %s", type(exc).__name__)
        await message.answer(MESSAGES.get("error", "حدث خطأ غير متوقع."))
