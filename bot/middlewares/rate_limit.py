from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.utils.logger import get_logger

logger = get_logger(__name__)

# Max messages allowed in the sliding window
MAX_MESSAGES = 20
# Window size in seconds
WINDOW_SECONDS = 60
# Hard block duration after exceeding limit (seconds)
BLOCK_SECONDS = 120


class RateLimitMiddleware(BaseMiddleware):
    """In-memory per-user sliding-window rate limiter.

    Prevents flood / abuse against the bot. Suitable for single-process
    deployments. For multi-worker setups replace the store with Redis.
    """

    def __init__(
        self,
        max_messages: int = MAX_MESSAGES,
        window_seconds: int = WINDOW_SECONDS,
        block_seconds: int = BLOCK_SECONDS,
    ) -> None:
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        # user_id -> deque of timestamps
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        # user_id -> unblock timestamp
        self._blocked_until: dict[int, float] = {}

    def _cleanup(self, user_id: int, now: float) -> None:
        hits = self._hits[user_id]
        cutoff = now - self.window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if not hits:
            self._hits.pop(user_id, None)

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

        user_id = user.id
        now = time.monotonic()

        # Permanent-style temporary block after abuse
        blocked_until = self._blocked_until.get(user_id)
        if blocked_until is not None:
            if now < blocked_until:
                remaining = int(blocked_until - now)
                await event.answer(
                    f"⏳ Too many requests. Please wait {remaining}s before trying again."
                )
                return None
            self._blocked_until.pop(user_id, None)

        self._cleanup(user_id, now)
        hits = self._hits[user_id]

        if len(hits) >= self.max_messages:
            self._blocked_until[user_id] = now + self.block_seconds
            logger.warning(
                "Rate limit exceeded telegram_id=%s (blocked for %ss)",
                user_id,
                self.block_seconds,
            )
            await event.answer(
                f"⏳ Too many requests. You are temporarily limited for {self.block_seconds}s."
            )
            return None

        hits.append(now)
        return await handler(event, data)
