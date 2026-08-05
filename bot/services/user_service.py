from __future__ import annotations

from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.repositories.user_repository import UserRepository
from bot.utils.logger import get_logger
from config import get_settings

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)
        self._settings = get_settings()

    async def get_or_create(self, tg_user: TgUser) -> User:
        user = await self._repo.get_by_telegram_id(tg_user.id)
        if user is not None:
            needs_update = (
                user.username != tg_user.username
                or user.full_name != tg_user.full_name
            )
            if needs_update:
                user = await self._repo.update(
                    tg_user.id,
                    username=tg_user.username,
                    full_name=tg_user.full_name,
                )
                logger.debug("Updated user profile telegram_id=%s", tg_user.id)
            return user  # type: ignore[return-value]

        is_admin = tg_user.id in self._settings.admin_ids
        user = await self._repo.create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            is_admin=is_admin,
        )
        logger.info("Registered new user telegram_id=%s is_admin=%s", tg_user.id, is_admin)
        return user

    async def is_admin(self, telegram_id: int) -> bool:
        if telegram_id in self._settings.admin_ids:
            return True
        user = await self._repo.get_by_telegram_id(telegram_id)
        if user is None:
            return False
        return bool(user.is_admin)

    async def is_blocked(self, telegram_id: int) -> bool:
        user = await self._repo.get_by_telegram_id(telegram_id)
        if user is None:
            return False
        return bool(user.is_blocked)

    async def get_stats(self) -> dict:
        total = await self._repo.count()
        return {"total_users": total}

    async def list_users(self, limit: int = 50) -> list[User]:
        # Hard cap to prevent large data exposure even for admins
        safe_limit = max(1, min(limit, 50))
        return list(await self._repo.get_all(limit=safe_limit))
