from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.utils.logger import get_logger

logger = get_logger(__name__)

MAX_USERNAME_LEN = 255
MAX_FULL_NAME_LEN = 255


def _sanitize_str(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:max_len]


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        try:
            result = await self._session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error("Failed to get user by telegram_id=%s: %s", telegram_id, exc)
            raise

    async def create(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
        is_admin: bool = False,
    ) -> User:
        try:
            user = User(
                telegram_id=telegram_id,
                username=_sanitize_str(username, MAX_USERNAME_LEN),
                full_name=_sanitize_str(full_name, MAX_FULL_NAME_LEN),
                is_admin=is_admin,
            )
            self._session.add(user)
            await self._session.commit()
            await self._session.refresh(user)
            logger.info("Created user telegram_id=%s", telegram_id)
            return user
        except Exception as exc:
            await self._session.rollback()
            logger.error("Failed to create user telegram_id=%s: %s", telegram_id, exc)
            raise

    async def update(
        self,
        telegram_id: int,
        *,
        username: str | None = None,
        full_name: str | None = None,
        is_admin: bool | None = None,
        is_blocked: bool | None = None,
    ) -> User | None:
        try:
            values: dict = {}
            if username is not None:
                values["username"] = _sanitize_str(username, MAX_USERNAME_LEN)
            if full_name is not None:
                values["full_name"] = _sanitize_str(full_name, MAX_FULL_NAME_LEN)
            if is_admin is not None:
                values["is_admin"] = is_admin
            if is_blocked is not None:
                values["is_blocked"] = is_blocked

            if not values:
                return await self.get_by_telegram_id(telegram_id)

            # Single round-trip: UPDATE … RETURNING *
            stmt = (
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(**values)
                .returning(User)
            )
            result = await self._session.execute(stmt)
            await self._session.commit()
            return result.scalar_one_or_none()
        except Exception as exc:
            await self._session.rollback()
            logger.error("Failed to update user telegram_id=%s: %s", telegram_id, exc)
            raise

    async def get_all(self, limit: int = 100, offset: int = 0) -> Sequence[User]:
        try:
            safe_limit = max(1, min(limit, 200))
            safe_offset = max(0, offset)
            result = await self._session.execute(
                select(User)
                .order_by(User.created_at.desc())
                .limit(safe_limit)
                .offset(safe_offset)
            )
            return result.scalars().all()
        except Exception as exc:
            logger.error("Failed to get all users: %s", exc)
            raise

    async def count(self) -> int:
        try:
            result = await self._session.execute(select(func.count()).select_from(User))
            return int(result.scalar_one())
        except Exception as exc:
            logger.error("Failed to count users: %s", exc)
            raise

    async def block_user(self, telegram_id: int) -> User | None:
        return await self.update(telegram_id, is_blocked=True)

    async def unblock_user(self, telegram_id: int) -> User | None:
        return await self.update(telegram_id, is_blocked=False)
