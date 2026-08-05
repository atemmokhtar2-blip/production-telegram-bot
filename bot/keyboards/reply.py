from __future__ import annotations

from aiogram.types import ReplyKeyboardRemove


def main_menu_keyboard() -> ReplyKeyboardRemove:
    """No reply keyboard — the product is focused on /create only."""
    return ReplyKeyboardRemove()


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
