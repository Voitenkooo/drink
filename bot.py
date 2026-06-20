import asyncio
import math
import json
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)

from supabase import create_client

# =========================================================
# CONFIG (⚠️ ЗАМЕНИ СЕКРЕТЫ И ПЕРЕВЫПУСТИ ИХ!)
# =========================================================

TOKEN = "8806146438:AAGLQE6KJaoPk5TITgpo4k_ushrNL3Kn_hg"
SUPABASE_URL = "https://snmlpsaieitdtndejyeb.supabase.co"
SUPABASE_KEY = "sb_secret_A0_2qsM_Vl_rozNLrgjBVQ_2ySF3gjq"
WEBAPP_URL = "https://voitenkooo.github.io/drink"

ADMIN_IDS = {6859689857}

bot = Bot(token=TOKEN)
dp = Dispatcher()
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# POST CHECK (FIX CRITICAL ERROR)
# =========================================================

def has_active_post(user_id: int) -> bool:
    try:
        res = sb.table("posts") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("active", True) \
            .execute()

        return bool(res.data)
    except Exception as e:
        print("has_active_post error:", e)
        return False

# =========================================================
# STATE (в будущем заменим на FSM, но сейчас оставим)
# =========================================================

user_step = {}
user_data = {}
user_lang = {}

# =========================================================
# I18N (простая система переводов)
# =========================================================

LANGS = ["ru", "ua", "en", "de"]

TEXTS = {
    "ru": {
        "welcome": "🍻 Добро пожаловать!",
        "menu": "🏠 Главное меню",
        "no_profile": "Анкеты нет ❌",
        "create_first": "Сначала создай анкету ❗",
        "invalid_age": "Возраст должен быть числом 16–99",
        "enter_name": "Введи имя 👤",
        "enter_age": "Возраст? 🎂",
        "enter_drinks": "Что ты пьёшь? 🍺",
        "send_photo": "Пришли фото 📸",
        "send_location": "Отправь геолокацию 📍",
    }
}


def t(user_id: int, key: str) -> str:
    lang = user_lang.get(user_id, "ru")
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)

# =========================================================
# HELPERS
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_json_safe(data):
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return []
    return []

# =========================================================
# UI KEYBOARDS (КРАСИВЫЕ И СТРУКТУРИРОВАННЫЕ)
# =========================================================
@dp.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    await message.answer("⚙️ Настройки", reply_markup=kb_settings)

def main_menu_kb(user_id: int):
    if has_active_post(user_id):
        buttons = [
            [KeyboardButton(text="👤 Моя анкета")],
            [KeyboardButton(text="👀 Люди рядом")],
            [KeyboardButton(text="🗺 Карта", web_app=WebAppInfo(url=WEBAPP_URL))],
            [KeyboardButton(text="⚙️ Настройки")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="🍻 Создать анкету")],
            [KeyboardButton(text="👀 Люди рядом")],
            [KeyboardButton(text="🗺 Карта", web_app=WebAppInfo(url=WEBAPP_URL))],
            [KeyboardButton(text="⚙️ Настройки")]
        ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


kb_back = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

kb_settings = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌍 Язык")],
        [KeyboardButton(text="🗑 Удалить анкету")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

kb_lang = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Русский"), KeyboardButton(text="Українська")],
        [KeyboardButton(text="English"), KeyboardButton(text="Deutsch")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

kb_time = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="15 мин")],
        [KeyboardButton(text="30 мин")],
        [KeyboardButton(text="60 мин")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

kb_location = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

kb_photo = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Добавить фото")],
        [KeyboardButton(text="📷 Удалить последнее фото")],
        [KeyboardButton(text="✅ Готово")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

# =========================================================
# CLEAN STEPS RESET
# =========================================================

def reset_user(user_id: int):
    user_step.pop(user_id, None)
    user_data.pop(user_id, None)

# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):
    reset_user(message.from_user.id)

    parts = message.text.split(maxsplit=1)
    payload = parts[1] if len(parts) > 1 else None

    if payload and payload.startswith("post_"):
        post_id = payload.replace("post_", "")

        post = sb.table("posts").select("*").eq("id", post_id).execute().data

        if post:
            p = post[0]
            await message.answer(
                f"🍻 <b>{p['name']}</b>\n🎂 {p['age']}\n🍺 {p['drinks']}",
                parse_mode="HTML"
            )
        return

    await message.answer(
        "🍻 Добро пожаловать!",
        reply_markup=main_menu_kb(message.from_user.id)
    )

@dp.message(F.text == "🍻 Создать анкету")
async def create_start(message: Message):
    uid = message.from_user.id

    if has_active_post(uid):
        await message.answer("❗ У тебя уже есть активная анкета")
        return

    user_step[uid] = "name"
    user_data[uid] = {"photos": []}

    await message.answer("👤 <b>Введи имя</b>", parse_mode="HTML", reply_markup=kb_back)


@dp.message(F.text == "⬅️ Назад")
async def back(message: Message):
    uid = message.from_user.id
    reset_user(uid)

    await message.answer("⬅️ Назад", reply_markup=main_menu_kb(uid))


@dp.message(F.text == "🏠 Главное меню")
async def home(message: Message):
    uid = message.from_user.id
    reset_user(uid)

    await message.answer("🏠 Главное меню", reply_markup=main_menu_kb(uid))


# =========================================================
# STEP HANDLER (ЕДИНЫЙ — ЭТО КРИТИЧНО)
# =========================================================

@dp.message(lambda m: m.from_user.id in user_step)
async def steps_handler(message: Message):
    uid = message.from_user.id
    text = message.text or ""

    step = user_step.get(uid)

    if step is None:
        return

    # ---------------- NAME
    if step == "name":
        if any(i.isdigit() for i in text):
            await message.answer("❌ Имя не должно содержать цифры")
            return

        user_data[uid]["name"] = text
        user_step[uid] = "age"

        await message.answer("🎂 Введи возраст")
        return

    # ---------------- AGE
    if step == "age":
        if not text.isdigit():
            await message.answer("❌ Только число")
            return

        age = int(text)
        if age < 16 or age > 99:
            await message.answer("❌ Возраст 16–99")
            return

        user_data[uid]["age"] = age
        user_step[uid] = "drinks"

        await message.answer("🍺 Что ты пьёшь?")
        return

    # ---------------- DRINKS
    if step == "drinks":
        user_data[uid]["drinks"] = text
        user_step[uid] = "photo"

        await message.answer(
            "📸 Пришли фото (до 3)",
            reply_markup=kb_photo
        )
        return

    # ---------------- PHOTO
    if step == "photo":

        # если пришло фото
        if message.photo:
            photos = user_data[uid]["photos"]

            if len(photos) >= 3:
                await message.answer("❌ Можно максимум 3 фото")
                return

            photos.append(message.photo[-1].file_id)

            await message.answer(
                f"📸 Добавлено ({len(photos)}/3)\n"
                "📸 Можешь добавить ещё или нажать ✅ Готово",
                reply_markup=kb_photo
            )
            return

        text = (message.text or "").strip()

        # пользователь нажал "добавить фото"
        if text == "📸 Добавить фото":
            await message.answer("📸 Отправь фото", reply_markup=kb_photo)
            return
            
        # удалить последнее фото
        if text == "📷 Удалить последнее фото":
            photos = user_data[uid]["photos"]

            if not photos:
                await message.answer("❌ Нет фото для удаления", reply_markup=kb_photo)
                return

            removed = photos.pop()

            await message.answer(
                f"🗑 Фото удалено\nОсталось: {len(photos)}",
                reply_markup=kb_photo
            )
            return

        # готово
        if text == "✅ Готово":
            photos = user_data[uid]["photos"]

            if len(photos) == 0:
                await message.answer("❌ Добавь хотя бы 1 фото")
                return

            user_step[uid] = "time"

            await message.answer(
                "⏳ Выбери время",
                reply_markup=kb_time
            )
            return

        await message.answer("📸 Отправь фото или нажми кнопку ниже", reply_markup=kb_photo)
        return

    # ---------------- TIME
    if step == "time":
        mapping = {
            "15 мин": 15,
            "30 мин": 30,
            "60 мин": 60
        }

        if text not in mapping:
            await message.answer("❌ Выбери кнопку")
            return

        user_data[uid]["ttl"] = mapping[text]
        user_step[uid] = "location"

        await message.answer("📍 Отправь геолокацию", reply_markup=kb_location)
        return

    # ---------------- LOCATION + SAVE
    if step == "location":
        if not message.location:
            await message.answer("📍 Используй кнопку геолокации")
            return

        data = user_data[uid]

        sb.table("posts").insert({
            "user_id": uid,
            "name": data["name"],
            "age": data["age"],
            "drinks": data["drinks"],
            "photos": json.dumps(data["photos"]),
            "lat": message.location.latitude,
            "lon": message.location.longitude,
            "active": True,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=data["ttl"])
            ).isoformat()
        }).execute()

        reset_user(uid)

        await message.answer(
            "✅ <b>Анкета создана!</b>\nТы теперь виден другим 👀",
            parse_mode="HTML",
            reply_markup=main_menu_kb(uid)
        )
        return

# =========================================================
# MY PROFILE (КРАСИВЫЙ + ИНФО + УПРАВЛЕНИЕ)
# =========================================================

def profile_kb(post_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📷 Фото", callback_data=f"photos_{post_id}")
        ],
        [
            InlineKeyboardButton(text="⏳ Продлить", callback_data=f"extend_{post_id}")
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{post_id}")
        ]
    ])


@dp.message(F.text == "👤 Моя анкета")
async def my_profile(message: Message):
    uid = message.from_user.id

    post = sb.table("posts") \
        .select("*") \
        .eq("user_id", uid) \
        .eq("active", True) \
        .execute().data

    if not post:
        await message.answer("❌ У тебя нет активной анкеты")
        return

    p = post[0]

    expires = datetime.fromisoformat(p["expires_at"])

    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    left = expires - datetime.now(timezone.utc)
    mins = max(0, int(left.total_seconds() // 60))

    caption = (
        "🍻 <b>ТВОЯ АНКЕТА</b>\n\n"
        f"👤 Имя: <b>{p['name']}</b>\n"
        f"🎂 Возраст: <b>{p['age']}</b>\n"
        f"🍺 Напиток: <b>{p['drinks']}</b>\n"
        f"⏳ Осталось: <b>{mins} мин</b>\n"
    )

    photos = parse_json_safe(p.get("photos"))

    if photos:
        await message.answer_photo(
            photo=photos[0],
            caption=caption,
            parse_mode="HTML",
            reply_markup=profile_kb(p["id"])
        )
    else:
        await message.answer(
            caption,
            parse_mode="HTML",
            reply_markup=profile_kb(p["id"])
        )


# =========================================================
# DELETE PROFILE
# =========================================================

@dp.callback_query(F.data.startswith("delete_"))
async def delete_profile(call: CallbackQuery):
    uid = call.from_user.id
    post_id = int(call.data.split("_")[1])

    sb.table("posts") \
        .update({"active": False}) \
        .eq("id", post_id) \
        .eq("user_id", uid) \
        .execute()

    await call.answer("🗑 Удалено")

    await bot.send_message(uid, "🗑 Анкета удалена")


# =========================================================
# EXTEND PROFILE (ВЫБОР ВРЕМЕНИ)
# =========================================================

extend_choice = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="15 мин"), KeyboardButton(text="30 мин")],
        [KeyboardButton(text="60 мин"), KeyboardButton(text="120 мин")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

extend_cache = {}


@dp.callback_query(F.data.startswith("extend_"))
async def extend_profile(call: CallbackQuery):
    uid = call.from_user.id
    post_id = int(call.data.split("_")[1])

    extend_cache[uid] = post_id

    await bot.send_message(
        uid,
        "⏳ Выбери время продления:",
        reply_markup=extend_choice
    )


@dp.message(F.text.in_(["15 мин", "30 мин", "60 мин", "120 мин"]))
async def extend_time(message: Message):
    if message.from_user.id in user_step:
        return
            
    uid = message.from_user.id

    post_id = extend_cache.get(uid)
    if not post_id:
        return

    mapping = {
        "15 мин": 15,
        "30 мин": 30,
        "60 мин": 60,
        "120 мин": 120
    }

    minutes = mapping[message.text]

    sb.table("posts") \
        .update({
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=minutes)
            ).isoformat(),
            "active": True
        }) \
        .eq("id", post_id) \
        .execute()

    extend_cache.pop(uid, None)

    await message.answer(f"⏳ Продлено на {minutes} мин", reply_markup=main_menu_kb(uid))


# =========================================================
# PHOTOS VIEW (FIXED)
# =========================================================

@dp.callback_query(F.data.startswith("photos_"))
async def show_photos(call: CallbackQuery):
    post_id = int(call.data.split("_")[1])

    post = sb.table("posts") \
        .select("photos") \
        .eq("id", post_id) \
        .execute().data

    if not post:
        await call.answer("Не найдено")
        return

    photos = json.loads(post[0].get("photos") or "[]")

    if len(photos) <= 1:
        await call.answer("Нет дополнительных фото")
        return

    for ph in photos[1:]:
        await bot.send_photo(call.from_user.id, ph)

    await call.answer()


# =========================================================
# PEOPLE NEARBY (FIXED + STABLE)
# =========================================================

@dp.message(F.text == "👀 Люди рядом")
async def people_nearby(message: Message):
    uid = message.from_user.id

    me = sb.table("posts") \
        .select("*") \
        .eq("user_id", uid) \
        .eq("active", True) \
        .execute().data

    if not me:
        await message.answer("❗ Сначала создай анкету")
        return

    me = me[0]

    posts = sb.table("posts") \
        .select("*") \
        .eq("active", True) \
        .execute().data

    found = False

    for p in posts:
        if p["user_id"] == uid:
            continue

        if p.get("lat") is None or p.get("lon") is None:
            continue

        d = haversine(me["lat"], me["lon"], p["lat"], p["lon"])

        if d > 10:
            continue

        found = True

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🍻 Встретиться", callback_data=f"meet_{p['id']}"),
                InlineKeyboardButton(text="📷 Фото", callback_data=f"photos_{p['id']}"),
            ],
            [
                InlineKeyboardButton(text="🚨 Жалоба", callback_data=f"report_{p['id']}"),
                InlineKeyboardButton(text="👎", callback_data="skip")
            ]
        ])

        photos = json.loads(p.get("photos") or "[]")

        text = (
            "🍻 <b>АНКЕТА</b>\n\n"
            f"👤 {p['name']}\n"
            f"🎂 {p['age']}\n"
            f"🍺 {p['drinks']}\n"
            f"📍 {round(d, 1)} км"
        )

        if photos:
            await message.answer_photo(
                photo=photos[0],
                caption=text,
                parse_mode="HTML",
                reply_markup=kb
            )
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)

    if not found:
        await message.answer("📍 Никого рядом нет")

@dp.callback_query(F.data.startswith("meet_"))
async def meet_request(call: CallbackQuery):
    uid = call.from_user.id
    post_id = int(call.data.split("_")[1])

    post = sb.table("posts") \
        .select("*") \
        .eq("id", post_id) \
        .execute().data

    if not post:
        await call.answer("Не найдено")
        return

    owner = post[0]["user_id"]

    if owner == uid:
        await call.answer("Это твоя анкета")
        return

    exists = sb.table("matches") \
        .select("*") \
        .or_(
            f"and(user1.eq.{uid},user2.eq.{owner}),and(user1.eq.{owner},user2.eq.{uid})"
        ) \
        .execute().data

    if exists:
        await call.answer("Уже отправлено")
        return

    sb.table("matches").insert({
        "user1": uid,
        "user2": owner,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍻 Принять", callback_data=f"accept_{uid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{uid}")
        ]
    ])

    await bot.send_message(owner, "🍻 Кто-то хочет встретиться!", reply_markup=kb)

    await call.answer("Запрос отправлен")


# =========================================================
# ACCEPT / DECLINE FIXED
# =========================================================

@dp.callback_query(F.data.startswith("accept_"))
async def accept_meet(call: CallbackQuery):
    uid = call.from_user.id
    other = int(call.data.split("_")[1])

    match = sb.table("matches") \
        .select("*") \
        .or_(
            f"and(user1.eq.{other},user2.eq.{uid})"
        ) \
        .eq("status", "pending") \
        .execute().data

    if not match:
        await call.answer("Нет запроса", show_alert=True)
        return

    sb.table("matches") \
        .update({"status": "accepted"}) \
        .eq("user1", other) \
        .eq("user2", uid) \
        .execute()

    await bot.send_message(other, "🎉 Встреча принята!")
    await bot.send_message(uid, "🎉 Ты подтвердил встречу")

    await call.answer()


@dp.callback_query(F.data.startswith("decline_"))
async def decline_meet(call: CallbackQuery):
    await call.answer("Отклонено")


@dp.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Users", callback_data="adm_users")],
        [InlineKeyboardButton(text="📄 Posts", callback_data="adm_posts")],
        [InlineKeyboardButton(text="🚨 Reports", callback_data="adm_reports")],
        [InlineKeyboardButton(text="🤝 Matches", callback_data="adm_matches")]
    ])

    await message.answer("⚙️ Admin panel", reply_markup=kb)


@dp.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    posts = sb.table("posts").select("user_id").execute().data
    users = list(set([p["user_id"] for p in posts]))

    await call.message.answer("👤 USERS:\n" + "\n".join(map(str, users[:50])))
    await call.answer()


@dp.callback_query(F.data == "adm_posts")
async def adm_posts(call: CallbackQuery):
    posts = sb.table("posts").select("*").limit(10).execute().data

    for p in posts:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Delete", callback_data=f"adm_del_{p['id']}")]
        ])

        await call.message.answer(
            f"👤 {p['name']} | 🎂 {p['age']} | 🍺 {p['drinks']}",
            reply_markup=kb
        )

    await call.answer()


@dp.callback_query(F.data.startswith("adm_del_"))
async def adm_delete(call: CallbackQuery):
    post_id = int(call.data.split("_")[2])

    sb.table("posts") \
        .delete() \
        .eq("id", post_id) \
        .execute()

    await call.answer("Удалено")


@dp.callback_query(F.data == "adm_reports")
async def adm_reports(call: CallbackQuery):
    reports = sb.table("reports").select("*").limit(20).execute().data

    text = "🚨 REPORTS:\n\n"
    for r in reports:
        text += f"{r['reporter']} ➝ {r['reported']}\n"

    await call.message.answer(text)
    await call.answer()


@dp.callback_query(F.data == "adm_matches")
async def adm_matches(call: CallbackQuery):
    matches = sb.table("matches").select("*").limit(20).execute().data

    text = "🤝 MATCHES:\n\n"
    for m in matches:
        text += f"{m['user1']} ↔ {m['user2']} ({m['status']})\n"

    await call.message.answer(text)
    await call.answer()

@dp.callback_query(F.data.startswith("report_"))
async def report_user(call: CallbackQuery):
    uid = call.from_user.id
    reported = int(call.data.split("_")[1])

    sb.table("reports").insert({
        "reporter": uid,
        "reported": reported,
        "reason": "user_report",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    await call.answer("🚨 Жалоба отправлена")

def set_lang(uid, text):
    if text == "Русский":
        user_lang[uid] = "ru"
    elif text == "Українська":
        user_lang[uid] = "ua"
    elif text == "English":
        user_lang[uid] = "en"
    elif text == "Deutsch":
        user_lang[uid] = "de"


@dp.message(F.text.in_(["Русский", "Українська", "English", "Deutsch"]))
async def lang(message: Message):
    set_lang(message.from_user.id, message.text)
    await message.answer("🌍 Язык установлен", reply_markup=main_menu_kb(message.from_user.id))

@dp.message(F.web_app_data)
async def webapp_handler(message: Message):
    import json
    try:
        data = json.loads(message.web_app_data.data)
    except:
        await message.answer("❌ Ошибка данных WebApp")
        return

    uid = message.from_user.id
    action = data.get("action")

    # ---------------- MEET
    if action == "meet":
        post_id = data.get("post_id")

        await message.answer("🍻 Запрос на встречу отправлен!")

        # тут можно сразу логировать или делать match request
        return

    # ---------------- REPORT
    if action == "report":
        reported = data.get("user_id")

        sb.table("reports").insert({
            "reporter": uid,
            "reported": reported,
            "reason": "webapp",
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        await message.answer("🚨 Жалоба отправлена")

        return

async def cleanup_loop():
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()

            sb.table("posts") \
                .update({"active": False}) \
                .lt("expires_at", now) \
                .execute()

        except Exception as e:
            print("cleanup error:", repr(e))

        await asyncio.sleep(60)

async def main():
    print("BOT STARTED")

    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(cleanup_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())