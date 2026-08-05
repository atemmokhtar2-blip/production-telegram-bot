from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.database.base import async_session_factory
from bot.services.user_service import UserService
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if user is None:
            return await handler(event, data)

        try:
            async with async_session_factory() as session:
                service = UserService(session)
                db_user = await service.get_or_create(user)
                data["db_user"] = db_user

                if db_user.is_blocked:
                    logger.warning(
                        "Blocked user attempted access telegram_id=%s", user.id
                    )
                    await event.answer("🚫 تم حظرك من استخدام هذا البوت.")
                    return None
        except Exception as exc:
            logger.exception(
                "Auth middleware failed for telegram_id=%s: %s",
                user.id,
                type(exc).__name__,
            )
            await event.answer("⚠️ خطأ مؤقت في الخدمة. حاول بعد لحظات.")
            return None

        return await handler(event, data)
