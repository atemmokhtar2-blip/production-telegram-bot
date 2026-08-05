SHOP_HANDLERS = r'''
PRODUCTS = [
    {"id": 1, "name": "منتج أ", "price": 50},
    {"id": 2, "name": "منتج ب", "price": 80},
    {"id": 3, "name": "منتج ج", "price": 120},
]
CARTS: dict[int, list[int]] = {}
ORDERS: list[dict] = []


class OrderStates(StatesGroup):
    name = State()
    phone = State()
    address = State()


@router.message(Command("products"))
@router.message(F.text == "🛍 المنتجات")
async def cmd_products(message: Message) -> None:
    lines = ["🛍 <b>المنتجات</b>\n"]
    for p in PRODUCTS:
        lines.append(
            f"{p['id']}) {p['name']} — {p['price']} ج\nأضف: /add_{p['id']}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text.regexp(r"^/add_(\d+)$"))
async def cmd_add(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    try:
        pid = int((message.text or "").split("_")[1])
    except Exception:
        await message.answer("رقم منتج غير صالح")
        return
    if not any(p["id"] == pid for p in PRODUCTS):
        await message.answer("المنتج غير موجود")
        return
    CARTS.setdefault(uid, []).append(pid)
    await message.answer("✅ تمت الإضافة للسلة. /cart لعرض السلة")


@router.message(Command("cart"))
@router.message(F.text == "🛒 السلة")
async def cmd_cart(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    items = CARTS.get(uid, [])
    if not items:
        await message.answer("السلة فارغة. /products")
        return
    total = 0
    lines = ["🛒 <b>سلتك</b>\n"]
    for pid in items:
        p = next(x for x in PRODUCTS if x["id"] == pid)
        total += p["price"]
        lines.append(f"- {p['name']} ({p['price']} ج)")
    lines.append(f"\n<b>الإجمالي: {total} ج</b>\n/order لإتمام الطلب")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("order"))
@router.message(F.text == "✅ إتمام الطلب")
async def cmd_order(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not CARTS.get(uid):
        await message.answer("السلة فارغة أولاً")
        return
    await state.set_state(OrderStates.name)
    await message.answer("اكتب اسمك الكامل:", reply_markup=ReplyKeyboardRemove())


@router.message(OrderStates.name)
async def order_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=(message.text or "").strip())
    await state.set_state(OrderStates.phone)
    await message.answer("رقم الهاتف:")


@router.message(OrderStates.phone)
async def order_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=(message.text or "").strip())
    await state.set_state(OrderStates.address)
    await message.answer("العنوان بالتفصيل:")


@router.message(OrderStates.address)
async def order_address(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    data = await state.get_data()
    items = CARTS.get(uid, [])
    total = sum(next(x for x in PRODUCTS if x["id"] == pid)["price"] for pid in items)
    order = {
        "user_id": uid,
        "name": data.get("name"),
        "phone": data.get("phone"),
        "address": (message.text or "").strip(),
        "items": list(items),
        "total": total,
    }
    ORDERS.append(order)
    CARTS[uid] = []
    await state.clear()
    await message.answer(
        f"✅ تم تسجيل طلبك رقم {len(ORDERS)}\nالإجمالي: {total} ج\nسنتواصل معك قريباً.",
        reply_markup=main_keyboard(),
    )


@router.message(Command("orders"))
async def cmd_orders_admin(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not is_admin(uid):
        await message.answer("🔒 للمشرفين فقط — أضف رقمك في ADMIN_IDS")
        return
    if not ORDERS:
        await message.answer("لا توجد طلبات بعد")
        return
    lines = ["📦 <b>آخر الطلبات</b>\n"]
    for i, o in enumerate(ORDERS[-15:], 1):
        lines.append(
            f"{i}) {o['name']} | {o['phone']}\n{o['address']}\nإجمالي: {o['total']} ج\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")
'''

BOOKING_HANDLERS = r'''
BOOKINGS: list[dict] = []


class BookStates(StatesGroup):
    day = State()
    time = State()
    contact = State()


@router.message(Command("book"))
@router.message(F.text == "📅 حجز موعد")
async def cmd_book(message: Message, state: FSMContext) -> None:
    await state.set_state(BookStates.day)
    await message.answer("اكتب يوم الحجز (مثال: الأحد 10/8):", reply_markup=ReplyKeyboardRemove())


@router.message(BookStates.day)
async def book_day(message: Message, state: FSMContext) -> None:
    await state.update_data(day=(message.text or "").strip())
    await state.set_state(BookStates.time)
    await message.answer("الساعة المفضلة:")


@router.message(BookStates.time)
async def book_time(message: Message, state: FSMContext) -> None:
    await state.update_data(time=(message.text or "").strip())
    await state.set_state(BookStates.contact)
    await message.answer("اسمك ورقم للتواصل:")


@router.message(BookStates.contact)
async def book_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    BOOKINGS.append({
        "day": data.get("day"),
        "time": data.get("time"),
        "contact": (message.text or "").strip(),
        "user_id": message.from_user.id if message.from_user else 0,
    })
    await state.clear()
    await message.answer("✅ تم الحجز. سنؤكد لك قريباً.", reply_markup=main_keyboard())
'''
