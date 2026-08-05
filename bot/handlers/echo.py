from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.database.models import User
from bot.localization import MESSAGES
from bot.states import CreateBotStates
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="echo")


@router.message(Command("profile"))
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
        logger.exception("Error in /profile: %s", type(exc).__name__)
        await message.answer(MESSAGES.get("error", "حدث خطأ."))


@router.message(F.text & ~F.text.startswith("/"))
async def free_text_to_create(message: Message, state: FSMContext) -> None:
    """Any plain text outside active trial/refine → start create flow with that text."""
    current = await state.get_state()
    if current is not None:
        return  # other stateful handlers own this message

    text = (message.text or "").strip()
    if not text:
        return

    # Hand off to create pipeline by setting state and re-using description processor
    await state.set_state(CreateBotStates.waiting_description)
    # Import here to avoid circular import at module load
    from bot.handlers.create_bot import process_bot_description

    await process_bot_description(message, state)
