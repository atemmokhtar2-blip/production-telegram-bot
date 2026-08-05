from __future__ import annotations

from aiogram import Router

from bot.handlers.admin import router as admin_router
from bot.handlers.create_bot import router as create_bot_router
from bot.handlers.echo import router as echo_router
from bot.handlers.help import router as help_router
from bot.handlers.start import router as start_router


def get_handlers_router() -> Router:
    router = Router(name="handlers")
    router.include_router(start_router)
    router.include_router(help_router)
    router.include_router(create_bot_router)
    router.include_router(admin_router)
    router.include_router(echo_router)
    return router
