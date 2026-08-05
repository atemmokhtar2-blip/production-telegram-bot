from __future__ import annotations

import re
import zipfile
from io import BytesIO

from bot.services.ai_service import AIService
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF-]+", "_", name.strip())[:40].strip("_")
    return s or "generated_bot"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_CONFIG_PY = '''from __future__ import annotations
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

_REQ = "aiogram==3.13.1\npython-dotenv==1.0.1\npydantic==2.9.2\npydantic-settings==2.5.2\n"

# Forbidden patterns = aiogram 2 / invalid
_BAD_PATTERNS = (
    "aiogram.contrib",
    "aiogram.dispatcher",
    "aiogram.utils.executor",
    "executor.start_polling",
    "Dispatcher(bot",
    "from aiogram.dispatcher",
)


def _strip_code_fences(raw: str) -> str:
    code = (raw or "").strip()
    if "```" in code:
        m = re.search(r"```(?:python)?\s*([\s\S]*?)```", code)
        if m:
            code = m.group(1).strip()
    # drop leading prose before first real import
    for marker in ("from __future__", "from aiogram", "from config", "import asyncio", "import logging"):
        i = code.find(marker)
        if i > 0:
            code = code[i:]
            break
        if i == 0:
            break
    # fix common broken first line: "import Bot, Dispatcher" -> from aiogram import ...
    first = code.split("\n", 1)[0]
    if first.startswith("import Bot") or first.startswith("import Dispatcher"):
        rest = code.split("\n", 1)[1] if "\n" in code else ""
        code = "from aiogram import Bot, Dispatcher, F, Router\n" + rest
    return code.strip()


def _is_aiogram3(code: str) -> bool:
    if any(p in code for p in _BAD_PATTERNS):
        return False
    return "aiogram" in code and "Router" in code or (
        "Dispatcher()" in code or "Dispatcher(storage" in code
    )


class ProjectBuilder:
    """Generate bot project purely from user description via AI (no templates)."""

    def __init__(self, ai: AIService | None = None) -> None:
        self._ai = ai or AIService()

    async def design_summary(self, description: str) -> str:
        try:
            raw = await self._ai.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "لخّص بوت تيليجرام من وصف المستخدم فقط. "
                            "نقاط عربية: الهدف، الأوامر، التدفقات. بدون كود وبدون HTML."
                        ),
                    },
                    {"role": "user", "content": description[:2500]},
                ],
                temperature=0.35,
            )
            return _escape_html((raw or description)[:2000])
        except Exception as exc:
            logger.warning("design_summary failed: %s", type(exc).__name__)
            return _escape_html(description[:500])

    def _system_prompt(self) -> str:
        return (
            "You write COMPLETE production Telegram bots using ONLY aiogram 3.x.\n"
            "CRITICAL — aiogram 3 API only:\n"
            "- from aiogram import Bot, Dispatcher, F, Router\n"
            "- from aiogram.filters import Command, CommandStart\n"
            "- from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup\n"
            "- from aiogram.fsm.context import FSMContext\n"
            "- from aiogram.fsm.state import State, StatesGroup\n"
            "- from aiogram.fsm.storage.memory import MemoryStorage\n"
            "- Router(), Dispatcher(storage=MemoryStorage()), dp.include_router(router)\n"
            "- await dp.start_polling(bot, drop_pending_updates=True)\n"
            "- NEVER use aiogram.contrib, dispatcher.FSMContext old path, or executor\n"
            "- from config import get_settings ; token = get_settings().bot_token\n"
            "Implement EXACTLY the user description (domain, flows, data). Arabic UI.\n"
            "Output ONLY valid Python source for main.py — no markdown, no comments about the task."
        )

    async def generate_main_py(self, description: str) -> str:
        raw = await self._ai.chat(
            [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": f"User description:\n{description[:3000]}\n\nWrite complete main.py now.",
                },
            ],
            temperature=0.2,
        )
        return _strip_code_fences(raw or "")

    async def _repair_main(self, description: str, broken: str, reason: str) -> str:
        raw = await self._ai.chat(
            [
                {
                    "role": "system",
                    "content": self._system_prompt()
                    + "\nFix the broken file. Return ONLY corrected main.py source.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Description:\n{description[:1500]}\n\n"
                        f"Problem:\n{reason}\n\n"
                        f"Broken code:\n{broken[:7000]}"
                    ),
                },
            ],
            temperature=0.1,
        )
        return _strip_code_fences(raw or "")

    def _validate(self, code: str) -> tuple[bool, str]:
        if not code or len(code) < 80:
            return False, "empty or too short"
        if not _is_aiogram3(code):
            return False, "not aiogram 3 (forbidden imports or missing Router/Dispatcher)"
        if "from aiogram import" not in code and "import aiogram" not in code:
            return False, "missing from aiogram import"
        if "get_settings" not in code and "BOT_TOKEN" not in code:
            # still ok if reads env — but we require config
            if "config" not in code:
                return False, "missing config/get_settings"
        try:
            compile(code, "main.py", "exec")
        except SyntaxError as e:
            return False, f"syntax: {e}"
        return True, "ok"

    async def build_project_zip(
        self, description: str, design_doc: str = "", project_name: str = "my_bot"
    ) -> tuple[bytes, dict[str, str], str]:
        design = design_doc or await self.design_summary(description)

        main_py = await self.generate_main_py(description)
        ok, reason = self._validate(main_py)
        if not ok:
            logger.warning("main.py invalid (%s) — repairing", reason)
            main_py = await self._repair_main(description, main_py, reason)
            ok, reason = self._validate(main_py)
            if not ok:
                # one more hard repair
                main_py = await self._repair_main(
                    description, main_py, reason + " | must be pure aiogram 3"
                )
                ok, reason = self._validate(main_py)
                if not ok:
                    raise RuntimeError(f"AI failed to produce valid main.py: {reason}")

        if "from config import get_settings" not in main_py and "get_settings" in main_py:
            pass
        elif "get_settings" not in main_py:
            main_py = "from config import get_settings\n" + main_py

        files = {
            "main.py": main_py,
            "config.py": _CONFIG_PY,
            "requirements.txt": _REQ,
            ".env.example": "BOT_TOKEN=your_token_here\nADMIN_IDS=\n",
            ".gitignore": ".env\n.venv/\n__pycache__/\n*.pyc\n",
            "README.md": (
                f"# بوت من وصف المستخدم\n\n## الوصف\n{description[:1000]}\n\n"
                f"## ملخص\n{design[:1500]}\n\n"
                "## تشغيل\n```bash\npip install -r requirements.txt\n"
                "cp .env.example .env\npython main.py\n```\n"
            ),
            "DESIGN.md": design,
        }
        return self._zip(files, project_name), files, design

    def _zip(self, files: dict[str, str], project_name: str) -> bytes:
        buf = BytesIO()
        root = _slug(project_name)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in files.items():
                clean = path.lstrip("./").replace("\\", "/")
                if ".." in clean or clean.startswith("/"):
                    continue
                zf.writestr(f"{root}/{clean}", content)
        return buf.getvalue()
