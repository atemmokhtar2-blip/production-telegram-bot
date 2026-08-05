from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

# Cached instances — keyboards are immutable; avoid reallocating on every /start
_MAIN_MENU: ReplyKeyboardMarkup | None = None
_REMOVE: ReplyKeyboardRemove | None = None


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    global _MAIN_MENU
    if _MAIN_MENU is None:
        _MAIN_MENU = ReplyKeyboardMarkup(
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
    return _MAIN_MENU


def remove_keyboard() -> ReplyKeyboardRemove:
    global _REMOVE
    if _REMOVE is None:
        _REMOVE = ReplyKeyboardRemove()
    return _REMOVE
