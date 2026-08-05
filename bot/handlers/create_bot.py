from __future__ import annotations

import re
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.agents import AgentPipeline
from bot.keyboards.create import after_create_keyboard, trial_keyboard
from bot.localization import MESSAGES
from bot.services.ai_service import AIService
from bot.services.project_builder import ProjectBuilder
from bot.states import CreateBotStates
from bot.utils.logger import get_logger

logger = get_logger(__name__)
router = Router(name="create_bot")

MAX_DESC_LEN = 3000
# in-memory zip cache keyed by user id (FSM data has size limits)
_ZIP_CACHE: dict[int, bytes] = {}
_DESIGN_CACHE: dict[int, str] = {}
_DESC_CACHE: dict[int, str] = {}


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF-]+", "_", text.strip())[:30].strip("_")
    return s or "my_bot"


@router.message(Command("create"))
@router.message(Command("newbot"))
async def cmd_create_bot(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateBotStates.waiting_description)
    await message.answer(
        MESSAGES.get(
            "create_bot_prompt",
            "🤖 اكتب وصف البوت بالتفصيل.",
        ),
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    _ZIP_CACHE.pop(uid, None)
    _DESIGN_CACHE.pop(uid, None)
    _DESC_CACHE.pop(uid, None)
    await message.answer(MESSAGES.get("create_bot_cancel", "تم الإلغاء."))


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
    status = await message.answer(
        "⏳ جاري تصميم البوت بالذكاء الاصطناعي...",
        parse_mode="HTML",
    )

    async def on_progress(name: str, index: int, total: int) -> None:
        try:
            await status.edit_text(
                f"⏳ {name}...",
                parse_mode="HTML",
            )
        except Exception:
            pass

    uid = message.from_user.id if message.from_user else 0
    try:
        pipeline = AgentPipeline()
        design = await pipeline.run(text, on_progress=on_progress)

        try:
            await status.edit_text("📦 جاري تجهيز ملفات المشروع (ZIP)...")
        except Exception:
            pass

        builder = ProjectBuilder()
        zip_bytes, _files = await builder.build_project_zip(
            text, design, project_name=_slug(text)
        )
        _ZIP_CACHE[uid] = zip_bytes
        _DESIGN_CACHE[uid] = design
        _DESC_CACHE[uid] = text

        # send design summary (chunked)
        try:
            await status.delete()
        except Exception:
            pass

        summary = design if len(design) <= 3500 else design[:3500] + "\n\n…(التفاصيل الكاملة داخل ملف ZIP)"
        await message.answer(summary[:4000])

        await message.answer(
            "✅ <b>تم إنشاء البوت</b>\n\n"
            "• <b>تجربة حية</b>: اكتب رسائل لتجربة ردود البوت المقترحة\n"
            "• <b>تعديل</b>: اطلب أي تغيير على التصميم أو الملفات\n"
            "• <b>ZIP</b>: استلم المشروع كاملاً على جهازك\n\n"
            "ابعت أي رسالة الآن للتجربة، أو استخدم الأزرار:",
            parse_mode="HTML",
            reply_markup=after_create_keyboard(),
        )
        await state.set_state(CreateBotStates.trial)
        logger.info("Project ready for user %s zip=%s bytes", uid, len(zip_bytes))
    except Exception as exc:
        logger.exception("create pipeline failed: %s", type(exc).__name__)
        try:
            await status.edit_text(MESSAGES.get("create_bot_fail", "فشل الإنشاء."))
        except Exception:
            await message.answer(MESSAGES.get("create_bot_fail", "فشل الإنشاء."))


@router.callback_query(F.data == "zip:send")
async def cb_send_zip(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    data = _ZIP_CACHE.get(uid)
    if not data:
        await callback.answer("لا يوجد مشروع جاهز. استخدم /create أولاً.", show_alert=True)
        return
    await callback.answer("جاري إرسال الملف...")
    name = _slug(_DESC_CACHE.get(uid, "my_bot")) + ".zip"
    doc = BufferedInputFile(data, filename=name)
    if callback.message:
        await callback.message.answer_document(
            doc,
            caption="📦 مشروع البوت جاهز.\n1) فك الضغط\n2) انسخ .env.example إلى .env\n3) ضع BOT_TOKEN\n4) pip install -r requirements.txt && python main.py",
        )


@router.callback_query(F.data == "trial:start")
async def cb_trial_start(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    if uid not in _DESIGN_CACHE:
        await callback.answer("لا يوجد بوت للتجربة. /create أولاً", show_alert=True)
        return
    await state.set_state(CreateBotStates.trial)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "🎮 <b>وضع التجربة الحية</b>\n"
            "ابعت أي رسالة أو أمر (مثل /start أو مرحبا) "
            "والبوت هيحاكي رد البوت اللي اتصمم لك.\n"
            "لو حابب تعدّل: اضغط ✏️ تعديل",
            parse_mode="HTML",
            reply_markup=trial_keyboard(),
        )


@router.callback_query(F.data == "trial:end")
async def cb_trial_end(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("انتهت التجربة")
    if callback.message:
        await callback.message.answer(
            "تم إنهاء التجربة. تقدر تحمّل ZIP أو تبدأ /create من جديد.",
            reply_markup=after_create_keyboard(),
        )


@router.callback_query(F.data == "refine:ask")
async def cb_refine_ask(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    if uid not in _DESIGN_CACHE:
        await callback.answer("لا يوجد مشروع. /create أولاً", show_alert=True)
        return
    await state.set_state(CreateBotStates.waiting_refine)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "✏️ اكتب التعديل المطلوب بوضوح.\n"
            "مثال: أضف أمر /prices وقائمة منتجات بالعربية"
        )


@router.message(CreateBotStates.waiting_refine, F.text)
async def process_refine(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    feedback = (message.text or "").strip()
    if not feedback or feedback.startswith("/"):
        await state.clear()
        return

    design = _DESIGN_CACHE.get(uid, "")
    desc = _DESC_CACHE.get(uid, "")
    status = await message.answer("⏳ جاري تطبيق التعديل وإعادة توليد الملفات...")

    try:
        ai = AIService()
        new_design = await ai.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "أنت مهندس بوتات. حدّث وثيقة التصميم حسب طلب التعديل. "
                        "أبقِ النتيجة منظمة بالعربية وجاهزة للتنفيذ."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"التصميم الحالي:\n{design[:6000]}\n\n"
                        f"الوصف الأصلي:\n{desc}\n\n"
                        f"طلب التعديل:\n{feedback}"
                    ),
                },
            ],
            temperature=0.4,
        )
        builder = ProjectBuilder()
        zip_bytes, _ = await builder.build_project_zip(
            desc + "\n\nتعديل: " + feedback, new_design, project_name=_slug(desc)
        )
        _ZIP_CACHE[uid] = zip_bytes
        _DESIGN_CACHE[uid] = new_design

        try:
            await status.delete()
        except Exception:
            pass

        preview = new_design if len(new_design) <= 3000 else new_design[:3000] + "…"
        await message.answer(f"✅ تم التحديث:\n\n{preview}")
        await message.answer(
            "تقدر تكمل التجربة أو تحمّل ZIP المحدّث:",
            reply_markup=after_create_keyboard(),
        )
        await state.set_state(CreateBotStates.trial)
    except Exception as exc:
        logger.exception("refine failed: %s", type(exc).__name__)
        await message.answer("❌ فشل التعديل. حاول صياغة الطلب بشكل أوضح.")
        await state.set_state(CreateBotStates.trial)


@router.message(CreateBotStates.trial, F.text)
async def trial_simulate(message: Message, state: FSMContext) -> None:
    """Simulate the generated bot's reply using AI + design context."""
    uid = message.from_user.id if message.from_user else 0
    design = _DESIGN_CACHE.get(uid)
    if not design:
        await state.clear()
        return

    user_text = (message.text or "").strip()
    if not user_text:
        return
    # allow zip/refine via text shortcuts
    if user_text in {"zip", "ZIP", "تحميل"}:
        data = _ZIP_CACHE.get(uid)
        if data:
            doc = BufferedInputFile(data, filename=_slug(_DESC_CACHE.get(uid, "bot")) + ".zip")
            await message.answer_document(doc, caption="📦 مشروعك")
        return

    try:
        ai = AIService()
        reply = await ai.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "أنت البوت النهائي الذي تم تصميمه. "
                        "رد كأنك البوت الحقيقي حسب التصميم التالي. "
                        "اختصر الرد ودعم العربية.\n\n"
                        f"التصميم:\n{design[:5000]}"
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            temperature=0.6,
        )
        await message.answer(reply or "...")
    except Exception as exc:
        logger.exception("trial sim failed: %s", type(exc).__name__)
        await message.answer("⚠️ فشل الرد التجريبي. حاول مرة أخرى أو حمّل ZIP.")
