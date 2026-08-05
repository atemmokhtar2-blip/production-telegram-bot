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
        logger.info("Admin stats requested by telegram_id=%s", message.from_user.id if message.from_user else "unknown")
    except Exception as exc:
        logger.exception("Error in /stats handler: %s", type(exc).__name__)
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
            # Never expose internal DB id; only telegram_id + public profile fields
            uname = f"@{u.username}" if u.username else "—"
            # Escape-like safety: Telegram HTML mode requires care, but we control the template
            safe_name = (u.full_name or "—").replace("<", "").replace(">", "")
            lines.append(
                f"• <code>{u.telegram_id}</code> {uname} — {safe_name}"
            )
        await message.answer("\n".join(lines), parse_mode="HTML")
        logger.info("Admin users list requested by telegram_id=%s", message.from_user.id if message.from_user else "unknown")
    except Exception as exc:
        logger.exception("Error in /users handler: %s", type(exc).__name__)
        await message.answer("An unexpected error occurred. Please try again later.")
