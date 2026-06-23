import asyncio
import math
import json
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, ReplyKeyboardRemove
)

from supabase import create_client

# =========================================================
# CONFIG
# =========================================================

TOKEN = "8806146438:AAGLQE6KJaoPk5TITgpo4k_ushrNL3Kn_hg"
SUPABASE_URL = "https://snmlpsaieitdtndejyeb.supabase.co"
SUPABASE_KEY = "sb_secret_A0_2qsM_Vl_rozNLrgjBVQ_2ySF3gjq"
WEBAPP_URL = "https://voitenkooo.github.io/drink"

ADMIN_IDS = {6859689857}

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# STATE (V2 CLEAN ARCHITECTURE)
# =========================================================

state_step = {}
state_data = {}
state_lang = {}
state_sessions = {}
state_extend = {}
state_interest = {}

# =========================================================
# I18N
# =========================================================

TEXTS = {
    "ru": {
        "welcome": "🍻 Добро пожаловать!",
        "menu": "🏠 Меню",
        "create": "🍻 Создать анкету",
        "profile": "👤 Анкета",
        "near": "👀 Рядом",
        "map": "🗺 Карта",
        "settings": "⚙️ Настройки",
        "back": "⬅️ Назад",
        "name": "Имя?",
        "age": "Возраст?",
        "drinks": "Напитки?",
        "photo": "Фото?",
        "time": "Время жизни анкеты",
        "location": "Геолокация",
        "created": "✅ Готово",
        "no_near": "📍 Никого рядом"
    }
}

def t(uid, key):
    lang = state_lang.get(uid, "ru")
    return TEXTS.get(lang, TEXTS["ru"]).get(key, key)

def set_lang(uid, lang):
    state_lang[uid] = lang

# =========================================================
# HELPERS
# =========================================================

def reset(uid):
    state_step.pop(uid, None)
    state_data.pop(uid, None)

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

def parse_json(x):
    if isinstance(x, list):
        return x
    try:
        return json.loads(x or "[]")
    except:
        return []

def is_admin(uid):
    return uid in ADMIN_IDS

# =========================================================
# DB HELPERS
# =========================================================

def get_active(uid):
    try:
        res = sb.table("posts").select("*").eq("user_id", uid).eq("active", True).execute()
        return res.data[0] if res.data else None
    except:
        return None

def has_active(uid):
    return get_active(uid) is not None

# =========================================================
# KEYBOARD
# =========================================================

def main_kb(uid):
    base = [
        [KeyboardButton(text="👀 Люди рядом")],
        [KeyboardButton(text="🗺 Карта", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton(text="⚙️ Настройки")]
    ]

    if has_active(uid):
        base.insert(0, [KeyboardButton(text="👤 Моя анкета")])
    else:
        base.insert(0, [KeyboardButton(text="🍻 Создать анкету")])

    return ReplyKeyboardMarkup(keyboard=base, resize_keyboard=True)

# =========================================================
# START
# =========================================================

@router.message(Command("start"))
async def start(message: Message):
    uid = message.from_user.id
    await message.answer(t(uid, "welcome"), reply_markup=main_kb(uid))

# =========================================================
# CREATE FLOW START
# =========================================================

@router.message(F.text == "🍻 Создать анкету")
async def create(message: Message):
    uid = message.from_user.id

    if has_active(uid):
        await message.answer("❗ Уже есть анкета")
        return

    state_step[uid] = "name"
    state_data[uid] = {"photos": []}

    await message.answer(t(uid, "name"), reply_markup=ReplyKeyboardRemove())

# =========================================================
# STEP ENGINE (PART START)
# =========================================================

@router.message(lambda m: m.from_user.id in state_step)
async def steps(message: Message):
    uid = message.from_user.id
    step = state_step.get(uid)
    text = message.text

    if step == "name":
        state_data[uid]["name"] = text
        state_step[uid] = "age"
        await message.answer(t(uid, "age"))
        return

    if step == "age":
        if not text.isdigit():
            await message.answer("❌ число")
            return

        state_data[uid]["age"] = int(text)
        state_step[uid] = "drinks"
        await message.answer(t(uid, "drinks"))
        return

    if step == "drinks":
        state_data[uid]["drinks"] = text
        state_step[uid] = "photo"
        await message.answer(t(uid, "photo"))
        return

    if step == "photo":
        if message.photo:
            photos = state_data[uid]["photos"]
            if len(photos) < 3:
                photos.append(message.photo[-1].file_id)
                await message.answer(f"📸 {len(photos)}/3")
            return

        if text == "➡️ Далее":
            state_step[uid] = "time"
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=x)] for x in ["15","30","60","120"]],
                resize_keyboard=True
            )
            await message.answer(t(uid,"time"), reply_markup=kb)
            return

# =========================================================
# TIME STEP
# =========================================================

    if step == "time":
        if text not in ["15", "30", "60", "120"]:
            await message.answer("❌ выбери кнопку")
            return

        state_data[uid]["ttl"] = int(text)
        state_step[uid] = "location"

        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📍 Отправить гео", request_location=True)]
            ],
            resize_keyboard=True
        )

        await message.answer(t(uid, "location"), reply_markup=kb)
        return

# =========================================================
# LOCATION + SAVE PROFILE
# =========================================================

    if step == "location":

        if not message.location:
            await message.answer("📍 нажми кнопку гео")
            return

        data = state_data[uid]

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
                datetime.now(timezone.utc)
                + timedelta(minutes=data["ttl"])
            ).isoformat()
        }).execute()

        reset(uid)

        await message.answer(
            t(uid, "created"),
            reply_markup=main_kb(uid)
        )

# =========================================================
# NEARBY ENTRY
# =========================================================

@router.message(F.text == "👀 Люди рядом")
async def nearby(message: Message):
    uid = message.from_user.id

    me = get_active(uid)
    if not me:
        await message.answer("❗ нет анкеты")
        return

    posts = sb.table("posts").select("*").eq("active", True).execute().data

    found = []

    for p in posts:
        if p["user_id"] == uid:
            continue

        if not p.get("lat") or not p.get("lon"):
            continue

        dist = haversine(me["lat"], me["lon"], p["lat"], p["lon"])

        if dist <= 10:
            found.append((p, dist))

    if not found:
        await message.answer(t(uid, "no_near"))
        return

    state_sessions[uid] = {
        "nearby": found,
        "index": 0
    }

    await send_near(uid)

# =========================================================
# SEND NEAR CARD
# =========================================================

async def send_near(uid: int):
    s = state_sessions.get(uid)

    if not s or s["index"] >= len(s["nearby"]):
        await bot.send_message(uid, "📍 конец списка")
        return

    p, dist = s["nearby"][s["index"]]

    photos = parse_json(p.get("photos"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍻 Meet", callback_data=f"meet_{p['id']}"),
            InlineKeyboardButton(text="👎 Skip", callback_data="skip")
        ],
        [
            InlineKeyboardButton(text="📷 Фото", callback_data=f"photos_{p['id']}")
        ],
        [
            InlineKeyboardButton(text="🚨 Report", callback_data=f"report_{p['user_id']}")
        ]
    ])

    text = (
        "🍻 PROFILE\n\n"
        f"👤 {p['name']}\n"
        f"🎂 {p['age']}\n"
        f"🍺 {p['drinks']}\n"
        f"📍 {round(dist,1)} km"
    )

    if photos:
        await bot.send_photo(uid, photos[0], caption=text, reply_markup=kb)
    else:
        await bot.send_message(uid, text, reply_markup=kb)

# =========================================================
# SKIP
# =========================================================

@router.callback_query(F.data == "skip")
async def skip(call: CallbackQuery):
    uid = call.from_user.id

    s = state_sessions.get(uid)
    if not s:
        await call.answer()
        return

    s["index"] += 1
    await call.answer("⏭")
    await send_near(uid)

# =========================================================
# PHOTO VIEW
# =========================================================

@router.callback_query(F.data.startswith("photos_"))
async def photos(call: CallbackQuery):
    post_id = int(call.data.split("_")[1])

    post = sb.table("posts").select("photos").eq("id", post_id).execute().data

    if not post:
        await call.answer("not found")
        return

    photos = parse_json(post[0].get("photos"))

    for ph in photos[1:]:
        await bot.send_photo(call.from_user.id, ph)

    await call.answer()

# =========================================================
# REPORT
# =========================================================

@router.callback_query(F.data.startswith("report_"))
async def report(call: CallbackQuery):
    uid = call.from_user.id
    reported = int(call.data.split("_")[1])

    sb.table("reports").insert({
        "reporter": uid,
        "reported": reported,
        "reason": "manual",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    await call.answer("🚨 ok")

# =========================================================
# MATCH HELPERS
# =========================================================

def match_exists(u1: int, u2: int):
    try:
        res = sb.table("matches") \
            .select("*") \
            .or_(
                f"and(from_user.eq.{u1},to_user.eq.{u2}),"
                f"and(from_user.eq.{u2},to_user.eq.{u1})"
            ) \
            .execute().data

        return bool(res)
    except:
        return False


def create_match(from_user: int, to_user: int):
    if from_user == to_user:
        return False

    if match_exists(from_user, to_user):
        return False

    sb.table("matches").insert({
        "from_user": from_user,
        "to_user": to_user,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    return True


# =========================================================
# MEET BUTTON (MAIN ENTRY)
# =========================================================

@router.callback_query(F.data.startswith("meet_"))
async def meet(call: CallbackQuery):
    from_user = call.from_user.id
    post_id = int(call.data.split("_")[1])

    post = sb.table("posts") \
        .select("*") \
        .eq("id", post_id) \
        .execute().data

    if not post:
        await call.answer("not found")
        return

    to_user = post[0]["user_id"]

    if from_user == to_user:
        await call.answer("self")
        return

    ok = create_match(from_user, to_user)

    if not ok:
        await call.answer("already sent")
        return

    try:
        await bot.send_message(
            to_user,
            "🍻 Кто-то заинтересовался тобой!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Посмотреть",
                        callback_data="interest_view"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить",
                        callback_data="interest_skip"
                    )
                ]
            ])
        )
    except:
        pass

    await call.answer("sent")


# =========================================================
# INTEREST SYSTEM (NOTIFICATION CACHE)
# =========================================================

async def add_interest(target_id: int):
    state_interest[target_id] = state_interest.get(target_id, 0) + 1

    try:
        await bot.send_message(
            target_id,
            f"🍻 Интерес к тебе: {state_interest[target_id]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Смотреть",
                        callback_data="interest_view"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить",
                        callback_data="interest_skip"
                    )
                ]
            ])
        )
    except:
        pass


# =========================================================
# ACCEPT / REJECT (SAFE MATCH UPDATE)
# =========================================================

@router.callback_query(F.data.startswith("accept_"))
async def accept(call: CallbackQuery):
    uid = call.from_user.id
    other = int(call.data.split("_")[1])

    match = sb.table("matches") \
        .select("*") \
        .eq("from_user", other) \
        .eq("to_user", uid) \
        .eq("status", "pending") \
        .execute().data

    if not match:
        await call.answer("no match")
        return

    sb.table("matches") \
        .update({"status": "accepted"}) \
        .eq("from_user", other) \
        .eq("to_user", uid) \
        .execute()

    try:
        await bot.send_message(other, "🎉 Match accepted!")
        await bot.send_message(uid, "🎉 You accepted!")
    except:
        pass

    await call.answer()


@router.callback_query(F.data.startswith("reject_"))
async def reject(call: CallbackQuery):
    uid = call.from_user.id
    other = int(call.data.split("_")[1])

    sb.table("matches") \
        .update({"status": "rejected"}) \
        .eq("from_user", other) \
        .eq("to_user", uid) \
        .execute()

    await call.answer("rejected")

# =========================================================
# BOT V2 - PART 4 (NEARBY + CARD ENGINE)
# =========================================================

# =========================================================
# NEARBY ENTRY
# =========================================================

@router.message(F.text == "👀 Люди рядом")
async def nearby_start(message: Message):
    uid = message.from_user.id

    me = get_active(uid)
    if not me:
        await message.answer("❗ сначала создай анкету")
        return

    posts = sb.table("posts").select("*").eq("active", True).execute().data

    found = []

    for p in posts:
        if p["user_id"] == uid:
            continue

        if not p.get("lat") or not p.get("lon"):
            continue

        dist = haversine(me["lat"], me["lon"], p["lat"], p["lon"])

        if dist <= 10:
            found.append((p, dist))

    if not found:
        await message.answer(t(uid, "no_near"))
        return

    user_data[uid] = {
        "nearby": found,
        "index": 0
    }

    await send_near_card(uid)

# =========================================================
# CARD SENDER (NEARBY SWIPE STYLE)
# =========================================================

async def send_near_card(uid: int):
    session = user_data.get(uid)

    if not session:
        return

    if session["index"] >= len(session["nearby"]):
        await bot.send_message(uid, "📍 конец списка")
        return

    p, dist = session["nearby"][session["index"]]

    photos = parse_json(p.get("photos"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍻 Meet", callback_data=f"meet_{p['id']}"),
            InlineKeyboardButton(text="👎 Skip", callback_data="near_skip")
        ],
        [
            InlineKeyboardButton(text="📷 Photos", callback_data=f"photos_{p['id']}")
        ],
        [
            InlineKeyboardButton(text="🚨 Report", callback_data=f"report_{p['user_id']}")
        ]
    ])

    text = (
        "🍻 <b>PROFILE</b>\n\n"
        f"👤 {p['name']}\n"
        f"🎂 {p['age']}\n"
        f"🍺 {p['drinks']}\n"
        f"📍 {round(dist, 1)} km"
    )

    if photos:
        await bot.send_photo(
            uid,
            photos[0],
            caption=text,
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await bot.send_message(
            uid,
            text,
            parse_mode="HTML",
            reply_markup=kb
        )

# =========================================================
# SKIP CARD
# =========================================================

@router.callback_query(F.data == "near_skip")
async def near_skip(call: CallbackQuery):
    uid = call.from_user.id

    session = user_data.get(uid)
    if not session:
        await call.answer()
        return

    session["index"] += 1

    await call.answer("⏭")
    await send_near_card(uid)

# =========================================================
# PHOTO VIEW (GLOBAL)
# =========================================================

@router.callback_query(F.data.startswith("photos_"))
async def photos_view(call: CallbackQuery):
    post_id = int(call.data.split("_")[1])

    post = sb.table("posts").select("photos").eq("id", post_id).execute().data

    if not post:
        await call.answer("not found")
        return

    photos = parse_json(post[0].get("photos"))

    if not photos:
        await call.answer("no photos")
        return

    for p in photos:
        await bot.send_photo(call.from_user.id, p)

    await call.answer()

# =========================================================
# REPORT SYSTEM (GLOBAL)
# =========================================================

@router.callback_query(F.data.startswith("report_"))
async def report_user(call: CallbackQuery):
    uid = call.from_user.id
    reported = int(call.data.split("_")[1])

    sb.table("reports").insert({
        "reporter": uid,
        "reported": reported,
        "reason": "manual",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    await call.answer("🚨 reported")

# =========================================================
# END PART 4
# =========================================================

# =========================================================
# BOT V2 - PART 5 (MATCH ENGINE)
# =========================================================

# =========================================================
# SAFE MATCH CHECK
# =========================================================

def match_exists(u1: int, u2: int):
    try:
        res = sb.table("matches").select("*").or_(
            f"and(from_user.eq.{u1},to_user.eq.{u2}),"
            f"and(from_user.eq.{u2},to_user.eq.{u1})"
        ).execute().data

        return bool(res)
    except:
        return False

# =========================================================
# CREATE MATCH (SAFE WRAPPER)
# =========================================================

def create_match(from_user: int, to_user: int):
    if from_user == to_user:
        return False

    if match_exists(from_user, to_user):
        return False

    sb.table("matches").insert({
        "from_user": from_user,
        "to_user": to_user,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    return True

# =========================================================
# MEET BUTTON (MAIN ENTRY)
# =========================================================

@router.callback_query(F.data.startswith("meet_"))
async def meet_user(call: CallbackQuery):
    from_user = call.from_user.id
    post_id = int(call.data.split("_")[1])

    post = sb.table("posts").select("*").eq("id", post_id).execute().data

    if not post:
        await call.answer("not found")
        return

    to_user = post[0]["user_id"]

    if from_user == to_user:
        await call.answer("self")
        return

    ok = create_match(from_user, to_user)

    if not ok:
        await call.answer("already sent")
        return

    try:
        await bot.send_message(
            to_user,
            "🍻 Кто-то заинтересовался тобой!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Посмотреть",
                        callback_data="interest_view"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить",
                        callback_data="interest_skip"
                    )
                ]
            ])
        )
    except:
        pass

    await call.answer("sent")

# =========================================================
# INTEREST CACHE TRIGGER (HOOK)
# =========================================================

async def add_interest(target_id: int, from_user: int):
    interest_cache[target_id] = interest_cache.get(target_id, 0) + 1
    count = interest_cache[target_id]

    try:
        await bot.send_message(
            target_id,
            f"🍻 Тобой заинтересовались: {count}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Посмотреть",
                        callback_data="interest_view"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить",
                        callback_data="interest_skip"
                    )
                ]
            ])
        )
    except:
        pass

# =========================================================
# SAFE WRAPPER (OPTIONAL)
# =========================================================

async def safe_meet(from_user: int, to_user: int):
    if match_exists(from_user, to_user):
        return False

    sb.table("matches").insert({
        "from_user": from_user,
        "to_user": to_user,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    return True

# =========================================================
# END PART 5
# =========================================================

# =========================================================
# BOT V2 - PART 6 (INTEREST SYSTEM)
# =========================================================

# =========================================================
# OPEN INTEREST FEED
# =========================================================

@router.callback_query(F.data == "interest_view")
async def interest_view(call: CallbackQuery):
    uid = call.from_user.id

    matches = sb.table("matches") \
        .select("*") \
        .eq("to_user", uid) \
        .eq("status", "pending") \
        .execute().data

    if not matches:
        await call.message.answer("📭 нет заявок")
        return

    user_data[uid] = {
        "interest": matches,
        "index": 0
    }

    await send_interest_card(uid)

# =========================================================
# INTEREST CARD (SWIPE STYLE)
# =========================================================

async def send_interest_card(uid: int):
    session = user_data.get(uid)

    if not session:
        return

    if session["index"] >= len(session["interest"]):
        await bot.send_message(uid, "📭 конец списка")
        return

    match = session["interest"][session["index"]]
    from_user = match["from_user"]

    post = sb.table("posts") \
        .select("*") \
        .eq("user_id", from_user) \
        .execute().data

    if not post:
        session["index"] += 1
        await send_interest_card(uid)
        return

    p = post[0]
    photos = parse_json(p.get("photos"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍻 Принять", callback_data=f"accept_{from_user}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{from_user}")
        ],
        [
            InlineKeyboardButton(text="📷 Фото", callback_data=f"photos_{p['id']}")
        ],
        [
            InlineKeyboardButton(text="🚨 Жалоба", callback_data=f"report_{p['user_id']}")
        ],
        [
            InlineKeyboardButton(text="⏭ Далее", callback_data="interest_next")
        ]
    ])

    text = (
        "🍻 <b>INTEREST</b>\n\n"
        f"👤 {p['name']}\n"
        f"🎂 {p['age']}\n"
        f"🍺 {p['drinks']}"
    )

    if photos:
        await bot.send_photo(
            uid,
            photos[0],
            caption=text,
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await bot.send_message(
            uid,
            text,
            parse_mode="HTML",
            reply_markup=kb
        )

# =========================================================
# NEXT CARD
# =========================================================

@router.callback_query(F.data == "interest_next")
async def interest_next(call: CallbackQuery):
    uid = call.from_user.id

    session = user_data.get(uid)
    if not session:
        return

    session["index"] += 1

    await call.answer()
    await send_interest_card(uid)

# =========================================================
# SKIP INTEREST MODE
# =========================================================

@router.callback_query(F.data == "interest_skip")
async def interest_skip(call: CallbackQuery):
    uid = call.from_user.id

    interest_cache[uid] = 0

    await call.answer("⏭")
    await call.message.answer("📭 пропущено")

# =========================================================
# ACCEPT MATCH (CORE LOGIC)
# =========================================================

@router.callback_query(F.data.startswith("accept_"))
async def accept_match(call: CallbackQuery):
    uid = call.from_user.id
    other = int(call.data.split("_")[1])

    match = sb.table("matches") \
        .select("*") \
        .eq("from_user", other) \
        .eq("to_user", uid) \
        .eq("status", "pending") \
        .execute().data

    if not match:
        await call.answer("no request")
        return

    sb.table("matches") \
        .update({"status": "accepted"}) \
        .eq("from_user", other) \
        .eq("to_user", uid) \
        .execute()

    try:
        await bot.send_message(other, "🎉 тебя приняли!")
        await bot.send_message(uid, "🎉 ты принял заявку!")
    except:
        pass

    await call.answer()

# =========================================================
# REJECT MATCH
# =========================================================

@router.callback_query(F.data.startswith("reject_"))
async def reject_match(call: CallbackQuery):
    uid = call.from_user.id
    other = int(call.data.split("_")[1])

    sb.table("matches") \
        .update({"status": "rejected"}) \
        .eq("from_user", other) \
        .eq("to_user", uid) \
        .execute()

    await call.answer("❌ rejected")

# =========================================================
# END PART 6
# =========================================================

# =========================================================
# BOT V2 - PART 7 (PROFILE CONTROL + CLEANUP)
# =========================================================

# =========================================================
# DELETE PROFILE
# =========================================================

@router.callback_query(F.data.startswith("delete_"))
async def delete_profile(call: CallbackQuery):
    uid = call.from_user.id
    post_id = int(call.data.split("_")[1])

    sb.table("posts") \
        .update({"active": False}) \
        .eq("id", post_id) \
        .eq("user_id", uid) \
        .execute()

    reset(uid)

    await call.answer("🗑 deleted")
    await bot.send_message(uid, "🗑 profile deleted")

# =========================================================
# EXTEND PROFILE START
# =========================================================

@router.callback_query(F.data.startswith("extend_"))
async def extend_profile(call: CallbackQuery):
    uid = call.from_user.id
    post_id = int(call.data.split("_")[1])

    extend_cache[uid] = post_id

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="15")],
            [KeyboardButton(text="30")],
            [KeyboardButton(text="60")],
            [KeyboardButton(text="120")],
            [KeyboardButton(text="⬅️ Back")]
        ],
        resize_keyboard=True
    )

    await bot.send_message(uid, "⏳ выбери время:", reply_markup=kb)

# =========================================================
# EXTEND APPLY
# =========================================================

@router.message(F.text.in_(["15", "30", "60", "120"]))
async def extend_time(message: Message):
    uid = message.from_user.id

    if uid in user_step:
        return

    post_id = extend_cache.get(uid)
    if not post_id:
        return

    minutes = int(message.text)

    sb.table("posts") \
        .update({
            "active": True,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=minutes)
            ).isoformat()
        }) \
        .eq("id", post_id) \
        .execute()

    extend_cache.pop(uid, None)

    await message.answer(f"⏳ продлено на {minutes} мин", reply_markup=main_kb(uid))

# =========================================================
# REPORT SYSTEM (FIXED SINGLE VERSION)
# =========================================================

@router.callback_query(F.data.startswith("report_"))
async def report_user(call: CallbackQuery):
    uid = call.from_user.id
    reported = int(call.data.split("_")[1])

    sb.table("reports").insert({
        "reporter": uid,
        "reported": reported,
        "reason": "manual",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    await call.answer("🚨 reported")

# =========================================================
# BACK BUTTON
# =========================================================

@router.message(F.text.in_(["⬅️ Back", "⬅️ Назад"]))
async def back(message: Message):
    uid = message.from_user.id
    reset(uid)
    await message.answer(t(uid, "back"), reply_markup=main_kb(uid))

# =========================================================
# HOME RESET
# =========================================================

@router.message(F.text.in_(["🏠 Menu", "🏠 Главное меню"]))
async def home(message: Message):
    uid = message.from_user.id
    reset(uid)
    await message.answer(t(uid, "menu"), reply_markup=main_kb(uid))

# =========================================================
# SETTINGS MENU
# =========================================================

@router.message(F.text.in_(["⚙️ Settings", "⚙️ Настройки"]))
async def settings(message: Message):
    uid = message.from_user.id

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌍 Language")],
            [KeyboardButton(text="🗑 Delete")],
            [KeyboardButton(text="⬅️ Back")]
        ],
        resize_keyboard=True
    )

    await message.answer(t(uid, "settings"), reply_markup=kb)

# =========================================================
# END PART 7
# =========================================================

# =========================================================
# BOT V2 - PART 8 (ADMIN PANEL)
# =========================================================

# =========================================================
# ADMIN PANEL ENTRY
# =========================================================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    uid = message.from_user.id

    if uid not in ADMIN_IDS:
        await message.answer("⛔ no access")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Users", callback_data="adm_users")],
        [InlineKeyboardButton(text="📄 Posts", callback_data="adm_posts")],
        [InlineKeyboardButton(text="🚨 Reports", callback_data="adm_reports")],
        [InlineKeyboardButton(text="🤝 Matches", callback_data="adm_matches")]
    ])

    await message.answer("⚙️ ADMIN PANEL", reply_markup=kb)

# =========================================================
# USERS LIST
# =========================================================

@router.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    posts = sb.table("posts").select("user_id").execute().data
    users = list(set(p["user_id"] for p in posts if p.get("user_id")))

    text = "👤 USERS:\n" + "\n".join(map(str, users[:50]))

    await call.message.answer(text)
    await call.answer()

# =========================================================
# POSTS VIEW
# =========================================================

@router.callback_query(F.data == "adm_posts")
async def adm_posts(call: CallbackQuery):
    posts = sb.table("posts").select("*").limit(10).execute().data

    for p in posts:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 delete", callback_data=f"adm_del_{p['id']}")]
        ])

        await call.message.answer(
            f"{p.get('name')} | {p.get('age')} | {p.get('drinks')}",
            reply_markup=kb
        )

    await call.answer()

# =========================================================
# DELETE POST (ADMIN)
# =========================================================

@router.callback_query(F.data.startswith("adm_del_"))
async def adm_delete(call: CallbackQuery):
    post_id = int(call.data.split("_")[2])

    sb.table("posts").delete().eq("id", post_id).execute()

    await call.answer("deleted")

# =========================================================
# REPORTS VIEW
# =========================================================

@router.callback_query(F.data == "adm_reports")
async def adm_reports(call: CallbackQuery):
    reports = sb.table("reports").select("*").limit(20).execute().data

    text = "🚨 REPORTS:\n\n"

    for r in reports:
        text += f"{r.get('reporter')} → {r.get('reported')}\n"

    await call.message.answer(text)
    await call.answer()

# =========================================================
# MATCHES VIEW
# =========================================================

@router.callback_query(F.data == "adm_matches")
async def adm_matches(call: CallbackQuery):
    matches = sb.table("matches").select("*").limit(20).execute().data

    text = "🤝 MATCHES:\n\n"

    for m in matches:
        text += f"{m.get('from_user')} ↔ {m.get('to_user')} ({m.get('status')})\n"

    await call.message.answer(text)
    await call.answer()

# =========================================================
# END PART 8
# =========================================================

# =========================================================
# BOT V2 - PART 9 (BACKGROUND + MAIN)
# =========================================================

# =========================================================
# CLEANUP POSTS (EXPIRE SYSTEM)
# =========================================================

async def cleanup_posts():
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()

            sb.table("posts") \
                .update({"active": False}) \
                .lt("expires_at", now) \
                .execute()

        except Exception as e:
            print("cleanup_posts error:", e)

        await asyncio.sleep(60)

# =========================================================
# CLEANUP MATCHES
# =========================================================

async def cleanup_matches():
    while True:
        try:
            sb.table("matches") \
                .delete() \
                .eq("status", "rejected") \
                .execute()

        except Exception as e:
            print("cleanup_matches error:", e)

        await asyncio.sleep(300)

# =========================================================
# OPTIONAL: INTEREST RESET LOOP
# =========================================================

async def reset_interest_cache():
    while True:
        try:
            interest_cache.clear()
        except:
            pass

        await asyncio.sleep(600)

# =========================================================
# BOT START
# =========================================================

async def main():
    print("🚀 BOT V2 STARTED")

    await bot.delete_webhook(drop_pending_updates=True)

    # background tasks
    asyncio.create_task(cleanup_posts())
    asyncio.create_task(cleanup_matches())
    asyncio.create_task(reset_interest_cache())

    # polling
    await dp.start_polling(bot)

# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())

# =========================================================
# END OF V2 FULL FILE
# =========================================================