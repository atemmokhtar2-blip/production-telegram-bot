from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database.base import async_session_factory
from bot.filters.admin import IsAdminFilter
from bot.localization import MESSAGES
from bot.services.user_service import UserService
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="admin")
router.message.filter(IsAdminFilter())


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    try:
        async with async_session_factory() as session:
            service = UserService(session)
            stats = await service.get_stats()
        text = MESSAGES["stats"].format(total_users=stats["total_users"])
        await message.answer(text, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /stats: %s", type(exc).__name__)
        await message.answer(MESSAGES.get("error", "حدث خطأ."))


@router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    try:
        async with async_session_factory() as session:
            service = UserService(session)
            users = await service.list_users(limit=20)
        if not users:
            await message.answer("لا يوجد مستخدمون.")
            return
        lines = [MESSAGES["users_list_header"]]
        for u in users:
            uname = f"@{u.username}" if u.username else "—"
            safe_name = (u.full_name or "—").replace("<", "").replace(">", "")
            lines.append(f"• <code>{u.telegram_id}</code> {uname} — {safe_name}")
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as exc:
        logger.exception("Error in /users: %s", type(exc).__name__)
        await message.answer(MESSAGES.get("error", "حدث خطأ."))
