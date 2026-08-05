from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="ℹ️ Help"),
                KeyboardButton(text="👤 Profile"),
            ],
            [
                KeyboardButton(text="📊 Stats"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose an option or type a message...",
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
