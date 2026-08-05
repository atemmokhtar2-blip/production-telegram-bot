from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.database.base import async_session_factory
from bot.services.user_service import UserService
from config import get_settings


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        if user is None:
            return False

        settings = get_settings()
        if user.id in settings.admin_ids:
            return True

        async with async_session_factory() as session:
            service = UserService(session)
            return await service.is_admin(user.id)
