from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from bot.services.ai_service import AIService
from bot.utils.logger import get_logger

logger = get_logger(__name__)

# Minimal production-ready scaffold; AI fills bot-specific pieces
_SCAFFOLD: dict[str, str] = {
    "requirements.txt": "\n".join(
        [
            "aiogram==3.13.1",
            "python-dotenv==1.0.1",
            "pydantic==2.9.2",
            "pydantic-settings==2.5.2",
        ]
    )
    + "\n",
    ".env.example": "BOT_TOKEN=your_token_here\nADMIN_IDS=\nLOG_LEVEL=INFO\n",
    ".gitignore": ".env\n__pycache__/\n*.pyc\n.venv/\nvenv/\nlogs/\n",
    "config.py": '''from __future__ import annotations
from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    bot_token: str = Field(default="")
    admin_ids: List[int] = Field(default_factory=list)
    log_level: str = Field(default="INFO")

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
''',
}


def _safe_slug(name: str) -> str:
    slug = re.sub(r"[^\w\u0600-\u06FF-]+", "_", name.strip())[:40].strip("_")
    return slug or "generated_bot"


class ProjectBuilder:
    """Builds a downloadable ZIP project from a user description + agent design."""

    def __init__(self, ai: AIService | None = None) -> None:
        self._ai = ai or AIService()

    async def generate_files(self, description: str, design_doc: str) -> dict[str, str]:
        """Ask AI to produce main.py + README + handlers outline as JSON map path->content."""
        system = (
            "أنت مولّد مشاريع بوتات تيليجرام. "
            "أرجع JSON فقط بدون markdown: كائن مفاتيحه مسارات ملفات وقيمه محتوى الملف نصاً. "
            "الملفات الإلزامية: main.py, README.md, bot/handlers/start.py, bot/handlers/help.py, "
            "bot/keyboards/reply.py, bot/localization/ar.py. "
            "الكود يجب أن يعمل مع aiogram 3.x و Python 3.12، ويدعم العربية. "
            "لا تضع BOT_TOKEN داخل الكود."
        )
        user = (
            f"وصف المستخدم:\n{description[:2000]}\n\n"
            f"ملخص التصميم:\n{design_doc[:4000]}\n\n"
            "ولّد الملفات الآن JSON فقط."
        )
        raw = await self._ai.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        files = self._parse_json_files(raw)
        # merge scaffold defaults
        out = dict(_SCAFFOLD)
        out.update(files)
        if "main.py" not in out:
            out["main.py"] = self._fallback_main()
        if "README.md" not in out:
            out["README.md"] = f"# Generated Bot\n\n{description[:500]}\n"
        return out

    def _parse_json_files(self, raw: str) -> dict[str, str]:
        text = raw.strip()
        # strip code fences if any
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if m:
                text = m.group(1).strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
        except Exception:
            logger.warning("Failed to parse AI project JSON")
        return {}

    def _fallback_main(self) -> str:
        return '''from __future__ import annotations
import asyncio, sys
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from config import get_settings

router = Router()

def menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="ℹ️ مساعدة")]],
        resize_keyboard=True,
    )

@router.message(CommandStart())
async def start(m: Message):
    await m.answer("أهلاً بك في البوت المُنشأ.", reply_markup=menu())

@router.message(Command("help"))
@router.message(F.text == "ℹ️ مساعدة")
async def help_cmd(m: Message):
    await m.answer("الأوامر: /start /help")

async def main():
    s = get_settings()
    if not s.bot_token:
        print("Set BOT_TOKEN in .env")
        sys.exit(1)
    bot = Bot(s.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
'''

    def build_zip(self, files: dict[str, str], project_name: str = "generated_bot") -> bytes:
        buf = BytesIO()
        root = _safe_slug(project_name)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in files.items():
                # normalize path
                clean = path.lstrip("./").replace("\\", "/")
                if clean.startswith("/"):
                    continue
                zf.writestr(f"{root}/{clean}", content)
            # always include design note
            if "DESIGN.md" not in files:
                zf.writestr(f"{root}/DESIGN.md", files.get("README.md", ""))
        return buf.getvalue()

    async def build_project_zip(
        self, description: str, design_doc: str, project_name: str = "my_bot"
    ) -> tuple[bytes, dict[str, str]]:
        files = await self.generate_files(description, design_doc)
        files["DESIGN.md"] = design_doc[:15000]
        zip_bytes = self.build_zip(files, project_name=project_name)
        return zip_bytes, files
