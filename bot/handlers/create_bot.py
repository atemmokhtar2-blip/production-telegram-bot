from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.agents import AgentPipeline
from bot.localization import MESSAGES
from bot.states import CreateBotStates
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="create_bot")

MAX_DESC_LEN = 3000


@router.message(Command("create"))
@router.message(Command("newbot"))
@router.message(F.text.in_({"🤖 إنشاء بوت", "إنشاء بوت", "اعمل بوت", "صمم بوت"}))
async def cmd_create_bot(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateBotStates.waiting_description)
    await message.answer(MESSAGES["create_bot_prompt"], parse_mode="HTML")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer(MESSAGES["create_bot_cancel"])


@router.message(CreateBotStates.waiting_description, F.text)
async def process_bot_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer(MESSAGES["create_bot_prompt"], parse_mode="HTML")
        return

    if text.startswith("/"):
        await state.clear()
        return

    if len(text) > MAX_DESC_LEN:
        text = text[:MAX_DESC_LEN]

    await state.clear()
    status = await message.answer(
        "⏳ جاري تشغيل <b>11 وكيل</b> لتصميم البوت...\n"
        "هذا قد يستغرق دقيقة أو أكثر.",
        parse_mode="HTML",
    )

    async def on_progress(name: str, index: int, total: int) -> None:
        try:
            await status.edit_text(
                f"⏳ الوكيل {index}/{total}: <b>{name}</b>...",
                parse_mode="HTML",
            )
        except Exception:
            pass

    try:
        pipeline = AgentPipeline()
        result = await pipeline.run(text, on_progress=on_progress)

        try:
            await status.delete()
        except Exception:
            pass

        chunk_size = 3500
        if len(result) <= 4000:
            await message.answer(result, parse_mode="HTML")
        else:
            # send without parse_mode for large plain chunks to avoid HTML breakage
            await message.answer("✅ تم اكتمال تصميم البوت بواسطة 11 وكيل:")
            for i in range(0, len(result), chunk_size):
                await message.answer(result[i : i + chunk_size])

        logger.info(
            "11-agent pipeline done telegram_id=%s",
            message.from_user.id if message.from_user else "?",
        )
    except Exception as exc:
        logger.exception("create_bot pipeline failed: %s", type(exc).__name__)
        try:
            await status.edit_text(MESSAGES["create_bot_fail"])
        except Exception:
            await message.answer(MESSAGES["create_bot_fail"])
