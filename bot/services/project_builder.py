from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO

from bot.services.ai_service import AIService
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF-]+", "_", name.strip())[:40].strip("_")
    return s or "generated_bot"


def _extract_commands(description: str) -> list[tuple[str, str]]:
    """Heuristic command list from description; always includes start/help."""
    cmds: list[tuple[str, str]] = [
        ("start", "بدء البوت"),
        ("help", "المساعدة"),
    ]
    text = description.lower()
    mapping = [
        (["منتج", "product", "سعر", "price", "متجر", "shop"], ("products", "عرض المنتجات")),
        (["طلب", "order", "سلة", "cart"], ("orders", "الطلبات")),
        (["حجز", "book", "موعد", "appointment"], ("book", "حجز موعد")),
        (["دعم", "support", "شكوى"], ("support", "الدعم")),
        (["ملف", "profile", "حساب"], ("profile", "ملفي")),
        (["إحصاء", "stats", "admin", "مشرف"], ("stats", "إحصائيات المشرف")),
    ]
    seen = {"start", "help"}
    for keys, pair in mapping:
        if any(k in text for k in keys) and pair[0] not in seen:
            cmds.append(pair)
            seen.add(pair[0])
    if len(cmds) == 2:
        cmds.append(("info", "معلومات"))
    return cmds[:8]


class ProjectBuilder:
    """Builds a complete runnable Telegram bot project as ZIP."""

    def __init__(self, ai: AIService | None = None) -> None:
        self._ai = ai or AIService()

    async def design_summary(self, description: str) -> str:
        try:
            return await self._ai.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "لخّص بوت تيليجرام من الوصف في نقاط عربية قصيرة: "
                            "الهدف، الأوامر، الجمهور. بدون كود."
                        ),
                    },
                    {"role": "user", "content": description[:2000]},
                ],
                temperature=0.4,
            )
        except Exception as exc:
            logger.warning("design_summary failed: %s", type(exc).__name__)
            return f"بوت حسب الطلب:\n{description[:500]}"

    def build_files(self, description: str, design: str) -> dict[str, str]:
        cmds = _extract_commands(description)
        cmd_handlers = []
        help_lines = []
        for name, title in cmds:
            help_lines.append(f"/{name} — {title}")
            if name in ("start", "help"):
                continue
            cmd_handlers.append(
                f'''
@router.message(Command("{name}"))
async def cmd_{name}(message: Message) -> None:
    await message.answer("📌 <b>{title}</b>\\n\\nتم تنفيذ الأمر حسب وصف مشروعك.", parse_mode="HTML")
'''
            )

        handlers_block = "\n".join(cmd_handlers)
        help_text = "\\n".join(help_lines)
        start_text = (
            "👋 أهلاً بك!\\n\\n"
            + description[:200].replace('"', "'").replace("\n", " ")
            + "\\n\\nاكتب /help للأوامر."
        )

        main_py = f'''# -*- coding: utf-8 -*-
"""Generated Telegram bot — edit freely."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = Router()


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ℹ️ مساعدة")],
        ],
        resize_keyboard=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "{start_text}",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ مساعدة")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>الأوامر</b>\\n\\n{help_text}",
        parse_mode="HTML",
    )
{handlers_block}

@router.message(F.text & ~F.text.startswith("/"))
async def echo(message: Message) -> None:
    text = (message.text or "").strip()
    if text:
        await message.answer(f"تم استلام رسالتك: {{text}}")


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token or "your_token" in settings.bot_token:
        logger.error("ضع BOT_TOKEN الحقيقي في ملف .env")
        sys.exit(1)
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
'''

        config_py = '''from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    bot_token: str = Field(default="")
    admin_ids: List[int] = Field(default_factory=list)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admins(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [int(x) for x in v]
        return [int(x.strip()) for x in str(v).split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
'''

        readme = f"""# بوت تيليجرام مُنشأ تلقائياً

## الوصف
{description[:1000]}

## التصميم
{design[:2000]}

## التشغيل
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# ضع توكن البوت من @BotFather في .env
python main.py
```

## الأوامر
{chr(10).join(f'- /{n}: {t}' for n, t in cmds)}
"""

        files = {
            "main.py": main_py,
            "config.py": config_py,
            "requirements.txt": "aiogram==3.13.1\npython-dotenv==1.0.1\npydantic==2.9.2\npydantic-settings==2.5.2\n",
            ".env.example": "BOT_TOKEN=your_token_here\nADMIN_IDS=\n",
            ".gitignore": ".env\n.venv/\n__pycache__/\n*.pyc\n",
            "README.md": readme,
            "DESIGN.md": design or description,
        }
        return files

    def build_zip(self, files: dict[str, str], project_name: str = "generated_bot") -> bytes:
        buf = BytesIO()
        root = _slug(project_name)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in files.items():
                clean = path.lstrip("./").replace("\\", "/")
                if ".." in clean or clean.startswith("/"):
                    continue
                zf.writestr(f"{root}/{clean}", content)
        return buf.getvalue()

    async def build_project_zip(
        self, description: str, design_doc: str = "", project_name: str = "my_bot"
    ) -> tuple[bytes, dict[str, str], str]:
        design = design_doc or await self.design_summary(description)
        files = self.build_files(description, design)
        zip_bytes = self.build_zip(files, project_name=project_name)
        return zip_bytes, files, design
