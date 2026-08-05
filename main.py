from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.database.base import init_db
from bot.handlers import get_handlers_router
from bot.middlewares import AuthMiddleware, LoggingMiddleware, RateLimitMiddleware
from bot.utils.logger import get_logger, setup_logging
from config import get_settings


async def main() -> None:
    setup_logging()
    logger = get_logger(__name__)

    settings = get_settings()

    if not settings.bot_token or settings.bot_token.startswith("123456"):
        logger.error("BOT_TOKEN is not set or is still the example value. Please configure .env")
        sys.exit(1)

    # Basic token format sanity check (Telegram bot tokens look like <digits>:<alphanum>)
    if ":" not in settings.bot_token or len(settings.bot_token) < 30:
        logger.error("BOT_TOKEN appears malformed. Please use a valid token from @BotFather")
        sys.exit(1)

    logger.info("Starting bot...")

    await init_db()
    logger.info("Database initialized")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Order matters: rate-limit first → logging → auth
    dp.message.middleware(RateLimitMiddleware())
    dp.update.middleware(LoggingMiddleware())
    dp.message.middleware(AuthMiddleware())

    dp.include_router(get_handlers_router())

    try:
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    # Let SystemExit propagate so process returns correct exit code
