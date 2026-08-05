from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO

from bot.services.ai_service import AIService
from bot.services.templates_shop import BOOKING_HANDLERS, SHOP_HANDLERS
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF-]+", "_", name.strip())[:40].strip("_")
    return s or "generated_bot"


def _detect_features(description: str) -> set[str]:
    text = description.lower()
    features: set[str] = {"core"}
    checks = {
        "shop": ["متجر", "منتج", "product", "سعر", "price", "shop", "store", "بيع", "مطعم", "كافيه"],
        "cart": ["سلة", "cart", "طلب", "order", "شراء"],
        "booking": ["حجز", "موعد", "book", "appointment", "عيادة", "صالون"],
        "support": ["دعم", "support", "شكوى", "تذكرة"],
        "admin": ["مشرف", "admin", "إحصاء", "stats", "طلبات"],
        "faq": ["رد آلي", "faq", "أسئلة", "استفسار"],
    }
    for feat, keys in checks.items():
        if any(k in text for k in keys):
            features.add(feat)
    if "shop" in features:
        features.update({"cart", "admin"})
    return features


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class ProjectBuilder:
    def __init__(self, ai: AIService | None = None) -> None:
        self._ai = ai or AIService()

    async def design_summary(self, description: str) -> str:
        try:
            raw = await self._ai.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "لخّص بوت تيليجرام من الوصف في نقاط عربية قصيرة: "
                            "الهدف، الأوامر، الجمهور. بدون كود وبدون رموز HTML."
                        ),
                    },
                    {"role": "user", "content": description[:2000]},
                ],
                temperature=0.3,
            )
            return _escape_html(raw or description[:400])
        except Exception as exc:
            logger.warning("design_summary failed: %s", type(exc).__name__)
            return _escape_html(f"بوت حسب الطلب:\n{description[:400]}")

    async def extract_products(self, description: str) -> list[dict]:
        """Try AI product list; fallback to sensible defaults from keywords."""
        try:
            raw = await self._ai.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "من وصف المتجر أرجع JSON array فقط بهذا الشكل: "
                            '[{"id":1,"name":"...","price":10}] '
                            "3 إلى 6 منتجات عربية بأسعار منطقية. بدون markdown."
                        ),
                    },
                    {"role": "user", "content": description[:1500]},
                ],
                temperature=0.2,
            )
            text = (raw or "").strip()
            if "```" in text:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
                if m:
                    text = m.group(1).strip()
            data = json.loads(text)
            products = []
            if isinstance(data, list):
                for i, item in enumerate(data[:8], start=1):
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or f"منتج {i}")[:40]
                    try:
                        price = int(float(item.get("price", 50)))
                    except Exception:
                        price = 50
                    products.append({"id": i, "name": name, "price": max(1, price)})
            if products:
                return products
        except Exception as exc:
            logger.warning("extract_products failed: %s", type(exc).__name__)
        return [
            {"id": 1, "name": "منتج أساسي", "price": 50},
            {"id": 2, "name": "منتج مميز", "price": 100},
            {"id": 3, "name": "عرض خاص", "price": 75},
        ]

    def _shop_handlers_with_products(self, products: list[dict]) -> str:
        products_literal = repr(products)
        # Replace the default PRODUCTS = [...] block
        return re.sub(
            r"PRODUCTS = \[.*?\]",
            f"PRODUCTS = {products_literal}",
            SHOP_HANDLERS,
            count=1,
            flags=re.S,
        )

    def build_files(
        self, description: str, design: str, products: list[dict] | None = None
    ) -> dict[str, str]:
        features = _detect_features(description)
        return {
            "main.py": self._render_main(description, features, products or []),
            "config.py": self._config_py(),
            "requirements.txt": (
                "aiogram==3.13.1\npython-dotenv==1.0.1\n"
                "pydantic==2.9.2\npydantic-settings==2.5.2\n"
            ),
            ".env.example": "BOT_TOKEN=your_token_here\nADMIN_IDS=\n",
            ".gitignore": ".env\n.venv/\n__pycache__/\n*.pyc\n",
            "README.md": self._readme(description, design, features),
            "DESIGN.md": design or description,
        }

    def _config_py(self) -> str:
        return '''from __future__ import annotations
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

    def _readme(self, description: str, design: str, features: set[str]) -> str:
        return (
            f"# بوت تيليجرام\n\n## الوصف\n{description[:800]}\n\n"
            f"## التصميم\n{design[:1500]}\n\n"
            f"## الميزات المكتشفة\n{', '.join(sorted(features))}\n\n"
            "## التشغيل\n```bash\npip install -r requirements.txt\n"
            "cp .env.example .env\n# ضع BOT_TOKEN\npython main.py\n```\n"
        )

    def _render_main(
        self, description: str, features: set[str], products: list[dict]
    ) -> str:
        short = description[:180].replace("\\", "/").replace('"', "'").replace("\n", " ")
        buttons: list[str] = []
        help_cmds = ["/start — بدء", "/help — مساعدة"]
        if "shop" in features:
            buttons.append('[KeyboardButton(text="🛍 المنتجات"), KeyboardButton(text="🛒 السلة")]')
            buttons.append('[KeyboardButton(text="✅ إتمام الطلب")]')
            help_cmds += [
                "/products — المنتجات",
                "/cart — السلة",
                "/order — إتمام الطلب",
                "/orders — طلبات المشرف",
            ]
        if "booking" in features:
            buttons.append('[KeyboardButton(text="📅 حجز موعد")]')
            help_cmds.append("/book — حجز موعد")
        if "support" in features or "faq" in features:
            buttons.append('[KeyboardButton(text="💬 الدعم")]')
            help_cmds.append("/support — الدعم")
        buttons.append('[KeyboardButton(text="ℹ️ مساعدة")]')
        rows = ",\n    ".join(buttons)
        help_body = "\\n".join(help_cmds)

        header = f'''# -*- coding: utf-8 -*-
"""Generated Telegram bot — fully runnable."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = Router()


def main_keyboard() -> ReplyKeyboardMarkup:
    rows = [
    {rows}
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 أهلاً بك!\\n\\n{short}\\n\\nاستخدم القائمة أو /help",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ مساعدة")
async def cmd_help(message: Message) -> None:
    await message.answer("📖 <b>الأوامر</b>\\n\\n{help_body}", parse_mode="HTML")

'''
        body = ""
        if "shop" in features:
            body += self._shop_handlers_with_products(
                products
                or [
                    {"id": 1, "name": "منتج أساسي", "price": 50},
                    {"id": 2, "name": "منتج مميز", "price": 100},
                    {"id": 3, "name": "عرض خاص", "price": 75},
                ]
            )
        if "booking" in features:
            body += BOOKING_HANDLERS
        if "support" in features or "faq" in features:
            body += '''
@router.message(F.text == "💬 الدعم")
@router.message(Command("support"))
async def cmd_support(message: Message) -> None:
    await message.answer("💬 اكتب استفسارك وسنرد عليك قريباً.\\nأو تواصل مع الإدارة.")

'''
        if features == {"core"}:
            body += f'''
@router.message(F.text)
async def about(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        return
    await message.answer(
        "ℹ️ هذا البوت مُعد حسب طلبك:\\n{short}\\n\\n/help للأوامر."
    )

'''
        footer = '''
@router.message(F.text & ~F.text.startswith("/"))
async def fallback(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        return
    await message.answer("استخدم القائمة أو /help لعرض الأوامر.")


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token or "your_token" in settings.bot_token:
        logger.error("ضع BOT_TOKEN الحقيقي في ملف .env")
        sys.exit(1)
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Bot started")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
'''
        # Avoid duplicate fallback if core about already handles F.text
        if features == {"core"}:
            footer = '''
async def main() -> None:
    settings = get_settings()
    if not settings.bot_token or "your_token" in settings.bot_token:
        logger.error("ضع BOT_TOKEN الحقيقي في ملف .env")
        sys.exit(1)
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Bot started")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
'''
        return header + body + footer

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
        features = _detect_features(description)
        products: list[dict] = []
        if "shop" in features:
            products = await self.extract_products(description)
        files = self.build_files(description, design, products=products)
        return self.build_zip(files, project_name=project_name), files, design
