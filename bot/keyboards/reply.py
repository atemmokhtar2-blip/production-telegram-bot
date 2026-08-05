from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

_MAIN_MENU: ReplyKeyboardMarkup | None = None
_REMOVE: ReplyKeyboardRemove | None = None


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    global _MAIN_MENU
    if _MAIN_MENU is None:
        _MAIN_MENU = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🤖 إنشاء بوت"),
                    KeyboardButton(text="ℹ️ مساعدة"),
                ],
                [
                    KeyboardButton(text="👤 ملفي"),
                    KeyboardButton(text="📊 إحصائيات"),
                ],
            ],
            resize_keyboard=True,
            input_field_placeholder="اختر من القائمة أو اكتب رسالة...",
        )
    return _MAIN_MENU


def remove_keyboard() -> ReplyKeyboardRemove:
    global _REMOVE
    if _REMOVE is None:
        _REMOVE = ReplyKeyboardRemove()
    return _REMOVE
