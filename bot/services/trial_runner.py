from __future__ import annotations

import asyncio
import os
import signal
import tempfile
from pathlib import Path

import aiohttp

from bot.utils.logger import get_logger

logger = get_logger(__name__)

# user_id -> (process, workdir)
_RUNNING: dict[int, tuple[asyncio.subprocess.Process, Path]] = {}


async def validate_token(token: str) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data["result"]
    except Exception as exc:
        logger.warning("validate_token failed: %s", type(exc).__name__)
    return None


async def start_trial(user_id: int, token: str, files: dict[str, str]) -> tuple[bool, str]:
    """Write project to temp dir and run main.py with user's token."""
    await stop_trial(user_id)

    # drop webhook so polling works
    try:
        async with aiohttp.ClientSession() as session:
            await session.get(
                f"https://api.telegram.org/bot{token}/deleteWebhook",
                params={"drop_pending_updates": "true"},
                timeout=aiohttp.ClientTimeout(total=15),
            )
    except Exception:
        pass

    work = Path(tempfile.mkdtemp(prefix=f"trial_{user_id}_"))
    for path, content in files.items():
        clean = path.lstrip("./").replace("\\", "/")
        if ".." in clean:
            continue
        fp = work / clean
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")

    env_path = work / ".env"
    env_path.write_text(f"BOT_TOKEN={token}\n", encoding="utf-8")

    # install deps in workdir venv would be slow — use system python + project reqs already installed
    proc = await asyncio.create_subprocess_exec(
        "python3",
        "main.py",
        cwd=str(work),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "BOT_TOKEN": token},
    )
    _RUNNING[user_id] = (proc, work)

    # wait briefly for crash
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
        out = b""
        if proc.stdout:
            out = await proc.stdout.read()
        _RUNNING.pop(user_id, None)
        return False, (out.decode("utf-8", errors="ignore")[-500:] or "فشل تشغيل البوت")
    except asyncio.TimeoutError:
        # still running = good
        return True, "ok"


async def stop_trial(user_id: int) -> None:
    entry = _RUNNING.pop(user_id, None)
    if not entry:
        return
    proc, work = entry
    try:
        proc.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
    except Exception:
        pass
    logger.info("Stopped trial for user %s work=%s", user_id, work)
