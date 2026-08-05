from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.create import after_create_keyboard
from bot.localization import MESSAGES
from bot.services.project_builder import ProjectBuilder
from bot.services.trial_runner import start_trial, stop_trial, validate_token
from bot.states import CreateBotStates
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="create_bot")

MAX_DESC_LEN = 3000
_ZIP_CACHE: dict[int, bytes] = {}
_FILES_CACHE: dict[int, dict[str, str]] = {}
_DESC_CACHE: dict[int, str] = {}
_DESIGN_CACHE: dict[int, str] = {}


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF-]+", "_", text.strip())[:30].strip("_")
    return s or "my_bot"


@router.message(Command("create"))
@router.message(Command("newbot"))
async def cmd_create_bot(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateBotStates.waiting_description)
    await message.answer(
        MESSAGES.get("create_bot_prompt", "🤖 اكتب وصف البوت بالتفصيل."),
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
@router.message(Command("stop_trial"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    await stop_trial(uid)
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer(MESSAGES.get("create_bot_cancel", "تم الإلغاء."))
    else:
        await message.answer("تم إيقاف أي تجربة شغالة.")


@router.message(CreateBotStates.waiting_description, F.text)
async def process_bot_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer(MESSAGES.get("create_bot_prompt", "اكتب الوصف."))
        return
    if text.startswith("/"):
        await state.clear()
        return
    if len(text) > MAX_DESC_LEN:
        text = text[:MAX_DESC_LEN]

    await state.clear()
    status = await message.answer("⏳ جاري إنشاء بوت كامل قابل للتشغيل...")

    uid = message.from_user.id if message.from_user else 0
    try:
        builder = ProjectBuilder()
        zip_bytes, files, design = await builder.build_project_zip(
            text, project_name=_slug(text)
        )
        _ZIP_CACHE[uid] = zip_bytes
        _FILES_CACHE[uid] = files
        _DESC_CACHE[uid] = text
        _DESIGN_CACHE[uid] = design

        try:
            await status.delete()
        except Exception:
            pass

        summary = design if len(design) <= 3000 else design[:3000] + "…"
        await message.answer(f"✅ <b>تم إنشاء البوت</b>\n\n{summary}", parse_mode="HTML")
        await message.answer(
            "اختر:\n"
            "• <b>تجربة حية</b>: ابعت توكن بوت من @BotFather وهنشغّله لك تجرّبه بنفسك\n"
            "• <b>تحميل ZIP</b>: استلم المشروع على جهازك",
            parse_mode="HTML",
            reply_markup=after_create_keyboard(),
        )
        logger.info("Project built user=%s files=%s zip=%s", uid, len(files), len(zip_bytes))
    except Exception as exc:
        logger.exception("build failed: %s", type(exc).__name__)
        try:
            await status.edit_text(MESSAGES.get("create_bot_fail", "فشل الإنشاء."))
        except Exception:
            await message.answer(MESSAGES.get("create_bot_fail", "فشل الإنشاء."))


@router.callback_query(F.data == "zip:send")
async def cb_send_zip(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    data = _ZIP_CACHE.get(uid)
    if not data:
        await callback.answer("لا يوجد مشروع. اكتب وصف بوت أولاً.", show_alert=True)
        return
    await callback.answer()
    name = _slug(_DESC_CACHE.get(uid, "my_bot")) + ".zip"
    doc = BufferedInputFile(data, filename=name)
    if callback.message:
        await callback.message.answer_document(
            doc,
            caption=(
                "📦 مشروعك جاهز\n"
                "1) فك الضغط\n"
                "2) انسخ .env.example إلى .env\n"
                "3) ضع BOT_TOKEN من @BotFather\n"
                "4) pip install -r requirements.txt && python main.py"
            ),
        )


@router.callback_query(F.data == "trial:start")
async def cb_trial_start(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    if uid not in _FILES_CACHE:
        await callback.answer("لا يوجد بوت. أنشئ واحد أولاً.", show_alert=True)
        return
    await state.set_state(CreateBotStates.waiting_trial_token)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "🎮 <b>التجربة الحية</b>\n\n"
            "1) افتح @BotFather\n"
            "2) أنشئ بوت جديد (/newbot) أو استخدم بوت عندك\n"
            "3) انسخ الـ <b>TOKEN</b> وابعتُه هنا الآن\n\n"
            "هنشغّل بوتك بهذا التوكن عشان تجربه بنفسك.\n"
            "للإيقاف: /stop_trial",
            parse_mode="HTML",
        )


@router.message(CreateBotStates.waiting_trial_token, F.text)
async def process_trial_token(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    token = (message.text or "").strip()
    # delete message with token for safety
    try:
        await message.delete()
    except Exception:
        pass

    if token.startswith("/"):
        await state.clear()
        return

    if ":" not in token or len(token) < 30:
        await message.answer("التوكن غير صالح. ابعت توكن صحيح من @BotFather")
        return

    files = _FILES_CACHE.get(uid)
    if not files:
        await state.clear()
        await message.answer("انتهت الجلسة. أنشئ بوت من جديد.")
        return

    status = await message.answer("⏳ جاري التحقق من التوكن وتشغيل بوتك...")
    info = await validate_token(token)
    if not info:
        await status.edit_text("❌ التوكن غير صحيح أو البوت غير متاح.")
        return

    username = info.get("username") or "your_bot"
    ok, err = await start_trial(uid, token, files)
    await state.clear()

    if not ok:
        await status.edit_text(f"❌ فشل تشغيل البوت:\n<code>{err[:400]}</code>", parse_mode="HTML")
        return

    await status.edit_text(
        f"✅ بوتك شغال للتجربة!\n\n"
        f"افتح: https://t.me/{username}\n"
        f"وابعت /start هناك وجرّب الأوامر بنفسك.\n\n"
        f"للإيقاف: /stop_trial\n"
        f"لتحميل المشروع: اضغط 📦 تحميل ZIP من الرسالة السابقة.",
    )
