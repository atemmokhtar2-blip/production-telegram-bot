from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.utils.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        update: Update | None = data.get("event_update")
        user = data.get("event_from_user")

        user_info = f"user_id={user.id}" if user else "unknown_user"
        update_id = update.update_id if update else "n/a"

        logger.info("Incoming update_id=%s %s", update_id, user_info)

        try:
            result = await handler(event, data)
            return result
        except Exception as exc:
            logger.exception(
                "Error while processing update_id=%s %s: %s",
                update_id,
                user_info,
                exc,
            )
            raise
