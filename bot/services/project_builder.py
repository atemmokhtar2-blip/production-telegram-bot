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


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")



_STD_IMPORTS = """from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from config import get_settings

logging.basicConfig(level=logging.INFO)
"""


def _ensure_imports(code: str) -> str:
    """Prepend required aiogram3 imports if the model omitted them."""
    code = code.strip()
    need = []
    if "from aiogram import" not in code:
        need.append(_STD_IMPORTS)
    elif "from config import get_settings" not in code and "get_settings" in code:
        code = "from config import get_settings\n" + code
    if need:
        # drop duplicate future imports inside body
        body = code
        for line in (
            "from __future__ import annotations",
            "import asyncio",
            "import logging",
            "from config import get_settings",
        ):
            body = body.replace(line + "\n", "")
        code = need[0] + "\n" + body
    if "async def main" not in code and "start_polling" in code:
        # wrap if model only left polling at module level wrongly — skip, validate will catch
        pass
    if 'if __name__ == "__main__"' not in code and "async def main" in code:
        code += '\n\nif __name__ == "__main__":\n    asyncio.run(main())\n'
    return code


def _strip_code(raw: str) -> str:
    code = (raw or "").strip()
    if "```" in code:
        m = re.search(r"```(?:python)?\s*([\s\S]*?)```", code)
        if m:
            code = m.group(1).strip()
    for marker in (
        "from __future__",
        "from aiogram",
        "from config",
        "import asyncio",
        "import logging",
    ):
        i = code.find(marker)
        if i > 0:
            code = code[i:]
            break
    first = code.split("\n", 1)[0]
    if first.startswith("import Bot") or first.startswith("import Dispatcher"):
        rest = code.split("\n", 1)[1] if "\n" in code else ""
        code = "from aiogram import Bot, Dispatcher, F, Router\n" + rest
    return code.strip()


def _extract_json(raw: str) -> dict | list | None:
    text = (raw or "").strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"[\{\[][\s\S]*[\}\]]", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


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

_BAD = (
    "aiogram.contrib",
    "aiogram.dispatcher",
    "executor.start_polling",
    "Dispatcher(bot",
    "keyboard.add(",
    "ReplyKeyboardMarkup(resize_keyboard=True)",
)


_AIOGRAM3_RULES = """
STRICT aiogram 3.x only:
- from aiogram import Bot, Dispatcher, F, Router
- from aiogram.filters import Command, CommandStart
- from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
- from aiogram.fsm.context import FSMContext
- from aiogram.fsm.state import State, StatesGroup
- from aiogram.fsm.storage.memory import MemoryStorage
- from config import get_settings
- Keyboard: ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="...")]], resize_keyboard=True)
- NEVER keyboard.add(), NEVER aiogram.contrib, NEVER Dispatcher(bot, ...)
- bot = Bot(token=get_settings().bot_token)
- dp = Dispatcher(storage=MemoryStorage()); dp.include_router(router)
- async def main(): await dp.start_polling(bot, drop_pending_updates=True)
- if __name__ == "__main__": import asyncio; asyncio.run(main())
- Per-user data: dict keyed by user_id, never one global cart for all users
"""


class ProjectBuilder:
    """Multi-stage AI pipeline: spec → code → review → fix."""

    def __init__(self, ai: AIService | None = None) -> None:
        self._ai = ai or AIService()

    async def design_summary(self, description: str) -> str:
        try:
            raw = await self._ai.chat(
                [
                    {
                        "role": "system",
                        "content": "لخّص البوت من الوصف: الهدف والأوامر والتدفقات. عربي مختصر بلا HTML.",
                    },
                    {"role": "user", "content": description[:2500]},
                ],
                temperature=0.3,
            )
            return _escape_html((raw or description)[:2000])
        except Exception:
            return _escape_html(description[:500])

    async def _build_spec(self, description: str) -> dict:
        raw = await self._ai.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a product analyst for Telegram bots. "
                        "From the user description ONLY, return JSON object with keys: "
                        "title (str), features (list of str), commands (list of {cmd, description}), "
                        "flows (list of str step-by-step), entities (list of data objects needed), "
                        "admin_features (list of str), sample_data (object with example items). "
                        "Be concrete and complete. Arabic values ok. JSON only."
                    ),
                },
                {"role": "user", "content": description[:3000]},
            ],
            temperature=0.25,
        )
        data = _extract_json(raw)
        if not isinstance(data, dict):
            data = {
                "title": "بوت",
                "features": [description[:200]],
                "commands": [
                    {"cmd": "start", "description": "بدء"},
                    {"cmd": "help", "description": "مساعدة"},
                ],
                "flows": [description[:300]],
                "entities": [],
                "admin_features": [],
                "sample_data": {},
            }
        return data

    async def _codegen(self, description: str, spec: dict) -> str:
        raw = await self._ai.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a senior aiogram 3 engineer. Write ONE complete main.py "
                        "that fully implements the SPEC. Every feature/command/flow must work. "
                        "Include realistic sample_data from the spec. Arabic UI.\n"
                        + _AIOGRAM3_RULES
                        + "\nOutput ONLY Python source."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Original description:\n{description[:2000]}\n\n"
                        f"SPEC JSON:\n{json.dumps(spec, ensure_ascii=False)[:5000]}\n\n"
                        "Write complete working main.py implementing ALL of the spec."
                    ),
                },
            ],
            temperature=0.15,
        )
        return _ensure_imports(_strip_code(raw or ""))

    async def _review(self, description: str, spec: dict, code: str) -> list[str]:
        raw = await self._ai.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You review Telegram bot code against a SPEC. "
                        "Return JSON array of missing or broken items (Arabic strings). "
                        "If complete and valid aiogram3, return []. JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Description:\n{description[:1200]}\n\n"
                        f"SPEC:\n{json.dumps(spec, ensure_ascii=False)[:3000]}\n\n"
                        f"CODE:\n{code[:8000]}"
                    ),
                },
            ],
            temperature=0.1,
        )
        data = _extract_json(raw)
        if isinstance(data, list):
            return [str(x) for x in data if x]
        return []

    async def _fix(self, description: str, spec: dict, code: str, issues: list[str]) -> str:
        raw = await self._ai.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Fix main.py so it fully satisfies the SPEC and issues list. "
                        "Return complete corrected main.py only.\n" + _AIOGRAM3_RULES
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Description:\n{description[:1500]}\n\n"
                        f"SPEC:\n{json.dumps(spec, ensure_ascii=False)[:3000]}\n\n"
                        f"Issues:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
                        f"Current code:\n{code[:8000]}"
                    ),
                },
            ],
            temperature=0.1,
        )
        return _ensure_imports(_strip_code(raw or code))

    def _validate(self, code: str) -> tuple[bool, str]:
        if not code or len(code) < 200:
            return False, "too short"
        if any(b in code for b in _BAD):
            return False, "forbidden aiogram2 or invalid keyboard API"
        if "from aiogram import" not in code:
            return False, "missing from aiogram import"
        if "Router" not in code:
            return False, "missing Router"
        if "start_polling" not in code:
            return False, "missing start_polling"
        # must not be start/help only
        handler_count = code.count("@router.message") + code.count("@dp.message")
        if handler_count < 4:
            return False, f"too few handlers ({handler_count})"
        try:
            compile(code, "main.py", "exec")
        except SyntaxError as e:
            return False, f"syntax: {e}"
        return True, "ok"

    async def build_project_zip(
        self, description: str, design_doc: str = "", project_name: str = "my_bot"
    ) -> tuple[bytes, dict[str, str], str]:
        design = design_doc or await self.design_summary(description)

        # Stage 1: SPEC
        logger.info("stage1 spec")
        spec = await self._build_spec(description)
        design = design or _escape_html(json.dumps(spec, ensure_ascii=False)[:1500])

        # Stage 2: CODEGEN
        logger.info("stage2 codegen")
        main_py = await self._codegen(description, spec)

        # Stage 3: validate + at most 2 repairs (avoid endless AI loops)
        ok, reason = self._validate(main_py)
        if not ok:
            logger.warning("validate fail: %s", reason)
            main_py = await self._fix(description, spec, main_py, [reason])
            ok, reason = self._validate(main_py)
            if not ok:
                main_py = await self._fix(
                    description, spec, main_py, [reason, "implement full SPEC"]
                )
                ok, reason = self._validate(main_py)
                if not ok:
                    raise RuntimeError(f"Failed to generate usable bot: {reason}")
        else:
            try:
                issues = await self._review(description, spec, main_py)
                if issues:
                    logger.warning("review issues: %s", issues[:5])
                    fixed = await self._fix(description, spec, main_py, issues)
                    if self._validate(fixed)[0]:
                        main_py = fixed
            except Exception as exc:
                logger.warning("review skipped: %s", type(exc).__name__)

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
                f"# {spec.get('title', 'بوت')}\n\n## الوصف\n{description[:1000]}\n\n"
                f"## الملخص\n{design[:1200]}\n\n"
                "## تشغيل\n```bash\npip install -r requirements.txt\n"
                "cp .env.example .env\npython main.py\n```\n"
            ),
            "DESIGN.md": design,
            "SPEC.json": json.dumps(spec, ensure_ascii=False, indent=2),
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
