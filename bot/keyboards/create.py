from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def after_create_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎮 تجربة حية", callback_data="trial:start"),
                InlineKeyboardButton(text="📦 تحميل ZIP", callback_data="zip:send"),
            ],
        ]
    )
