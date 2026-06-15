import asyncio
import math
import json
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
    WebAppInfo
)

from supabase import create_client

# ---------------- CONFIG
TOKEN = "8806146438:AAGLQE6KJaoPk5TITgpo4k_ushrNL3Kn_hg"
SUPABASE_URL = "https://snmlpsaieitdtndejyeb.supabase.co"
SUPABASE_KEY = "sb_secret_A0_2qsM_Vl_rozNLrgjBVQ_2ySF3gjq"
WEBAPP_URL = "https://voitenkooo.github.io/drink"

bot = Bot(token=TOKEN)
dp = Dispatcher()
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- STATE
user_step = {}
user_data = {}
user_lang = {}

def btn(user_id, key):
    lang = user_lang.get(user_id, "ru")
    return texts[key][lang]
    
texts = {
    "menu": {
        "ru": "🏠 Главное меню",
        "ua": "🏠 Головне меню",
        "en": "🏠 Main menu",
    },
    "create": {
        "ru": "🍻 Создать заявку",
        "ua": "🍻 Створити заявку",
        "en": "🍻 Create request",
    },
    "nearby": {
        "ru": "👀 Люди рядом",
        "ua": "👀 Люди поруч",
        "en": "👀 Nearby people",
    },
    "no_profile": {
        "ru": "❗ Сначала создай заявку",
        "ua": "❗ Спочатку створи анкету",
        "en": "❗ Create profile first",
    },
    "profile_created": {
        "ru": "✅ Анкета создана!",
        "ua": "✅ Анкету створено!",
        "en": "✅ Profile created!",
    },
    "age_error": {
        "ru": "Возраст только числом",
        "ua": "Вік тільки числом",
        "en": "Age must be a number",
    },
    "settings": {
        "ru": "⚙️ Настройки",
        "ua": "⚙️ Налаштування",
        "en": "⚙️ Settings",
    },
    "language": {
        "ru": "🌍 Язык установлен",
        "ua": "🌍 Мову встановлено",
        "en": "🌍 Language set",
    }
}

def t(user_id, key):
    lang = user_lang.get(user_id, "ru")
    return texts.get(lang, texts["ru"]).get(key, key)

# ---------------- CHECK ACTIVE POST
def has_active_post(user_id):
    res = sb.table("posts") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("active", True) \
        .execute().data
    return len(res) > 0

# ---------------- KEYBOARDS
kb_nav = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🏠 Главное меню")]],
    resize_keyboard=True
)

kb_settings = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌍 Язык")],
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
        [KeyboardButton(text="Анкета на 15 минут")],
        [KeyboardButton(text="Анкета на 30 минут")],
        [KeyboardButton(text="Анкета на 60 минут")],
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

# ---------------- MAIN MENU
def get_kb(user_id):
    if has_active_post(user_id):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👤 Моя анкета")],
                [KeyboardButton(text=btn(user_id, "nearby"))],
                [KeyboardButton(text="🗺 Карта", web_app=WebAppInfo(url=WEBAPP_URL))],
                [KeyboardButton(text="⚙️ Настройки")]
            ],
            resize_keyboard=True
        )

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=btn(user_id, "create"))],
            [KeyboardButton(text=btn(user_id, "nearby"))],
            [KeyboardButton(text="🗺 Карта", web_app=WebAppInfo(url=WEBAPP_URL))],
            [KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )

# ---------------- DISTANCE
def dist(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) ** 2
    )

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def send_meet_request(from_user, to_user):

    exists = sb.table("matches") \
        .select("*") \
        .eq("user1", from_user) \
        .eq("user2", to_user) \
        .execute()

    if exists.data:
        return False

    sb.table("matches").insert({
        "user1": from_user,
        "user2": to_user,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    return True

# ---------------- START
@dp.message(CommandStart(deep_link=True))
async def start(message: Message, command: CommandObject):

    data = command.args

    if data and data.startswith("chat_"):
        other_user_id = data.split("_")[1]

        await message.answer(
            f"💬 Чат открыт с пользователем {other_user_id}"
        )
        return

    await message.answer(
        "🍻 Добро пожаловать!",
        reply_markup=get_kb(message.from_user.id)
    )

@dp.message()
async def handler(message: Message):

    user_id = message.from_user.id
    text = message.text or ""

    step = user_step.get(user_id)

    if step is None and (message.photo or message.location):
        await message.answer("Сначала выбери действие из меню")
        return

    # ---------------- MAIN MENU
    if text == "🏠 Главное меню":
        user_step.pop(user_id, None)
        user_data.pop(user_id, None)
        await message.answer(t(user_id, "menu"), reply_markup=get_kb(user_id))
        return

    # ---------------- SETTINGS
    if text == "⚙️ Настройки":
        await message.answer(btn(user_id, "settings"), reply_markup=kb_settings)
        return

    if text == "🌍 Язык":
        await message.answer(btn(user_id, "language"), reply_markup=kb_lang)
        return


    lang_map = {
        "Русский": "ru",
        "Українська": "ua",
        "English": "en",
        "Deutsch": "en"
    }

    if text in lang_map:
        user_lang[user_id] = lang_map[text]
        await message.answer("🌍 Язык установлен", reply_markup=get_kb(user_id))
        return

    # ---------------- CREATE POST START
    KeyboardButton(text=btn(user_id, "create"))

    if has_active_post(user_id):
        await message.answer(btn(user_id, "no_profile"))
        return

        user_step[user_id] = "name"
        user_data[user_id] = {}

        await message.answer("👤 Введи имя", reply_markup=kb_nav)
        return

    # ---------------- STEPS
    step = user_step.get(user_id)

    if step == "name":

        if any(c.isdigit() for c in text):
            await message.answer("Имя только буквами")
            return

        user_data[user_id]["name"] = text
        user_step[user_id] = "age"

        await message.answer("🎂 Возраст?")
        return

    if step == "age":

        if not text.isdigit():
            await message.answer(t(user_id, "age_error"))
            return

        age = int(text)

        if age < 18 or age > 99:
            await message.answer("Возраст 18–99")
            return

        user_data[user_id]["age"] = age
        user_step[user_id] = "drinks"

        await message.answer("🍺 Что пьёшь?")
        return

    if step == "drinks":

        user_data[user_id]["drinks"] = text
        user_step[user_id] = "photo"

        await message.answer("📸 Пришли фото")
        return

    if step == "photo":

        if not message.photo:
            await message.answer("Пришли фото")
            return

        user_data[user_id]["photo"] = message.photo[-1].file_id
        user_step[user_id] = "time"

        await message.answer("⏳ Выбери время", reply_markup=kb_time)
        return

    if step == "time":

        mapping = {"15 минут": 15, "30 минут": 30, "60 минут": 60}

        if text not in mapping:
            await message.answer("Выбери кнопку")
            return

        user_data[user_id]["ttl"] = mapping[text]
        user_step[user_id] = "location"

        await message.answer("📍 Отправь геолокацию", reply_markup=kb_location)
        return

    if step == "location":

        if not message.location:
            await message.answer("Используй геолокацию")
            return

        data = user_data[user_id]

        sb.table("posts").insert({
            "user_id": user_id,
            "username": message.from_user.username,
            "name": data["name"],
            "age": data["age"],
            "drinks": data["drinks"],
            "photo": data.get("photo"),
            "lat": message.location.latitude,
            "lon": message.location.longitude,
            "active": True,
            "expires_at": (
                datetime.now(timezone.utc) +
                timedelta(minutes=data["ttl"])
            ).isoformat()
        }).execute()

        user_step.pop(user_id, None)
        user_data.pop(user_id, None)

        await message.answer("✅ Анкета создана!", reply_markup=get_kb(user_id))
        return

    # ---------------- PEOPLE NEARBY (FIXED)
    if text == "👀 Люди рядом":

        me = sb.table("posts") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("active", True) \
            .execute().data

        if not me:
            await message.answer("❗ Сначала создай заявку")
            return

        me = me[0]

        posts = sb.table("posts") \
            .select("*") \
            .eq("active", True) \
            .execute().data

        found = False

        for p in posts:

            if p["user_id"] == user_id:
                continue

            if not p.get("lat") or not p.get("lon"):
                continue

            d = dist(me["lat"], me["lon"], p["lat"], p["lon"])

            found = True

            caption = f"""
🍻 АНКЕТА

👤 {p['name']}
🎂 {p['age']} лет
🍺 {p['drinks']}

📍 {round(d, 1)} км от тебя
"""

            kb_like = types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text="🍻 Предложить встречу",
                        callback_data=f"meet_{p['id']}"
                    ),
                    types.InlineKeyboardButton(
                        text="👎",
                        callback_data="skip"
                    ),
                    types.InlineKeyboardButton(
                        text="🚨",
                        callback_data=f"report_{p['user_id']}"
                    )
                ]]
            )

            if p.get("photo"):
                await message.answer_photo(p["photo"], caption=caption, reply_markup=kb_like)
            else:
                await message.answer(caption, reply_markup=kb_like)

        if not found:
            await message.answer("📍 Пока никого нет")

        return

    # ---------------- MY PROFILE
    if message.text == "👤 Моя анкета":

        post = sb.table("posts") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("active", True) \
            .execute().data

        if not post:
            await message.answer("❌ Анкеты нет")
            return

        p = post[0]

        expires = datetime.fromisoformat(p["expires_at"]).replace(tzinfo=timezone.utc)
        left = expires - datetime.now(timezone.utc)
        minutes = max(0, int(left.total_seconds() // 60))

        caption = f"""

🍻 ТВОЯ АНКЕТА

👤 Имя: {p.get('name')}
🎂 Возраст: {p.get('age')}
🍺 Напиток: {p.get('drinks')}

⏳ Осталось: {minutes} мин
📍 Статус: активна
"""

        if p.get("photo"):
            await message.answer_photo(photo=p["photo"], caption=caption)
        else:
            await message.answer(caption)

        return

# ---------------- CALLBACKS
@dp.callback_query()
async def cb(call: CallbackQuery):

    user_id = call.from_user.id
    data = call.data

    # SKIP
    if data == "skip":
        await call.answer("Следующий")
        return

    # REPORT
    if data.startswith("report_"):

        reported = int(data.split("_")[1])

        sb.table("reports").insert({
            "reporter": user_id,
            "reported": reported,
            "reason": "user_report"
        }).execute()

        await call.answer("Жалоба отправлена")
        return

    if data.startswith("meet_"):

        post_id = int(data.split("_")[1])

        post = (
            sb.table("posts")
            .select("*")
            .eq("id", post_id)
            .execute()
            .data
        )

        if not post:
            await call.answer("Не найдено")
            return

        owner = post[0]["user_id"]

        created = send_meet_request(
            from_user=user_id,
            to_user=owner
        )

        if not created:
            await call.answer("Запрос уже отправлен")
            return

        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🍻 Иду",
                        callback_data=f"accept_{user_id}"
                    ),
                    types.InlineKeyboardButton(
                        text="❌ Нет",
                        callback_data=f"decline_{user_id}"
                    )
                ]
            ]
        )

        await bot.send_message(
            owner,
            "🍻 Кто-то хочет встретиться",
            reply_markup=kb
        )

        await call.answer("Отправлено")
        return

    # ACCEPT
    if data.startswith("accept_"):

        other = int(data.split("_")[1])

        BOT_USERNAME = "drink_nearby_bot"
        link = f"https://t.me/{BOT_USERNAME}?start=chat_{other}"

        await bot.send_message(
            other,
            f"🎉 Встреча подтверждена!\n💬 Чат: {link}"
        )

        await bot.send_message(
            user_id,
            "🎉 Встреча подтверждена"
        )

        await call.answer("Подтверждено")
        return

    # DECLINE
    if data.startswith("decline_"):

        await call.answer("Отклонено")
        return


# ---------------- CLEANUP (auto disable expired posts)
async def cleanup():
    while True:
        try:
            sb.table("posts") \
                .update({"active": False}) \
                .lt("expires_at", datetime.now(timezone.utc).isoformat()) \
                .execute()

        except Exception as e:
            print("Cleanup error:", e)

        await asyncio.sleep(30)


# ---------------- MAIN
async def main():
    asyncio.create_task(cleanup())
    await dp.start_polling(bot)


# ---------------- START BOT
if __name__ == "__main__":
    asyncio.run(main())