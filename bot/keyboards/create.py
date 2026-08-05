from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def after_create_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎮 تجربة حية", callback_data="trial:start"),
                InlineKeyboardButton(text="📦 تحميل ZIP", callback_data="zip:send"),
            ],
            [
                InlineKeyboardButton(text="✏️ طلب تعديل", callback_data="refine:ask"),
            ],
        ]
    )


def trial_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 تحميل ZIP", callback_data="zip:send"),
                InlineKeyboardButton(text="✏️ تعديل", callback_data="refine:ask"),
            ],
            [
                InlineKeyboardButton(text="✅ إنهاء التجربة", callback_data="trial:end"),
            ],
        ]
    )
