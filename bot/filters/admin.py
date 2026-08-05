from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.database.base import async_session_factory
from bot.database.models import User
from bot.services.user_service import UserService
from config import get_settings


class IsAdminFilter(BaseFilter):
    """Strict admin check: environment ADMIN_IDS takes precedence,
    then the is_admin flag stored in the database.
    Prefer db_user injected by AuthMiddleware to avoid an extra query.
    """

    async def __call__(
        self,
        event: Message | CallbackQuery,
        db_user: User | None = None,
    ) -> bool:
        user = event.from_user
        if user is None:
            return False

        settings = get_settings()
        if user.id in settings.admin_ids_set:
            return True

        # Reuse already-loaded user from AuthMiddleware when available
        if db_user is not None:
            return bool(db_user.is_admin)

        try:
            async with async_session_factory() as session:
                service = UserService(session)
                return await service.is_admin(user.id)
        except Exception:
            return False
