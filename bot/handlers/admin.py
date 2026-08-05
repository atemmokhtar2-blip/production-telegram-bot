from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.base import async_session_factory
from bot.filters.admin import IsAdminFilter
from bot.localization.en import MESSAGES
from bot.services.user_service import UserService
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="admin")
router.message.filter(IsAdminFilter())


@router.message(Command("stats"))
@router.message(F.text == "📊 Stats")
async def cmd_stats(message: Message) -> None:
    try:
        async with async_session_factory() as session:
            service = UserService(session)
            stats = await service.get_stats()
        text = MESSAGES["stats"].format(total_users=stats["total_users"])
        await message.answer(text, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /stats handler: %s", exc)
        await message.answer("An unexpected error occurred. Please try again later.")


@router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    try:
        async with async_session_factory() as session:
            service = UserService(session)
            users = await service.list_users(limit=20)

        if not users:
            await message.answer("No users found.")
            return

        lines = [MESSAGES["users_list_header"]]
        for u in users:
            uname = f"@{u.username}" if u.username else "—"
            lines.append(
                f"• <code>{u.telegram_id}</code> {uname} — {u.full_name or '—'}"
            )
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /users handler: %s", exc)
        await message.answer("An unexpected error occurred. Please try again later.")
