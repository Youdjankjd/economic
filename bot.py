import json
import random
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import aiosqlite

BOT_TOKEN = "7776073776:AAFFQldws5uyyMYG3ORAVanaazy41D5SZPE"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === Работа с БД ===
async def init_db():
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            ref_by INTEGER,
            referrals INTEGER DEFAULT 0,
            last_daily TEXT
        )""")
        await db.commit()

async def get_user(tg_id, username, ref_by=None):
    async with aiosqlite.connect("db.sqlite") as db:
        cursor = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        user = await cursor.fetchone()

        if not user:
            await db.execute(
                "INSERT INTO users (tg_id, username, ref_by, last_daily) VALUES (?, ?, ?, ?)",
                (tg_id, username, ref_by, "1970-01-01")
            )
            if ref_by:
                await db.execute("UPDATE users SET referrals = referrals + 1, balance = balance + 15 WHERE tg_id = ?", (ref_by,))
        await db.commit()

async def add_money(tg_id, amount):
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE tg_id = ?", (amount, tg_id))
        await db.commit()

async def remove_money(tg_id, amount):
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE tg_id = ?", (amount, tg_id))
        await db.commit()

async def get_balance(tg_id):
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0

async def get_top():
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 50") as c:
            return await c.fetchall()

async def get_top_refs():
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 50") as c:
            return await c.fetchall()

async def get_referrals(tg_id):
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT referrals FROM users WHERE tg_id = ?", (tg_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0

async def get_last_daily(tg_id):
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT last_daily FROM users WHERE tg_id = ?", (tg_id,)) as c:
            row = await c.fetchone()
            return datetime.fromisoformat(row[0]) if row else datetime(1970, 1, 1)

async def update_daily_time(tg_id):
    now = datetime.now().isoformat()
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("UPDATE users SET last_daily = ? WHERE tg_id = ?", (now, tg_id))
        await db.commit()

# === Команды ===

@dp.message(Command("start"))
async def start(message: Message):
    args = message.text.split()
    ref_by = None
    if len(args) > 1 and args[1].isdigit():
        ref_by = int(args[1])
        if ref_by == message.from_user.id:
            ref_by = None

    await get_user(message.from_user.id, message.from_user.username or "noname", ref_by)
    await message.answer("👋 Привет! Ты можешь работать, играть, приглашать друзей и быть в топе!\n\n🪙 /jobs – выбрать работу\n🎰 /coin <ставка> <орел/решка>\n🎁 /daily – рулетка до 5000 монет\n💎 /shop – магазин\n💰 /balance\n📈 /top\n👥 /ref – рефералка\n👑 /top_refs – топ по приглашениям")

@dp.message(Command("balance"))
async def balance(message: Message):
    bal = await get_balance(message.from_user.id)
    await message.reply(f"💰 У тебя {bal} монет")

@dp.message(Command("top"))
async def top(message: Message):
    top_users = await get_top()
    msg = "🏆 Топ 50 по монетам:\n"
    for i, (username, bal) in enumerate(top_users, 1):
        msg += f"{i}. @{username} — {bal}💰\n"
    await message.reply(msg)

@dp.message(Command("top_refs"))
async def top_refs(message: Message):
    top_refs = await get_top_refs()
    msg = "👥 Топ по рефералам:\n"
    for i, (username, count) in enumerate(top_refs, 1):
        msg += f"{i}. @{username} — {count} приглашений\n"
    await message.reply(msg)

@dp.message(Command("ref"))
async def ref_info(message: Message):
    await get_user(message.from_user.id, message.from_user.username or "noname")
    count = await get_referrals(message.from_user.id)
    link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.reply(f"👤 Ты пригласил: {count} чел.\n🔗 Твоя ссылка: {link}")

# === Работа ===
jobs = {
    "таксист": (70, 120),
    "дальнобойщик": (100, 180),
    "уборщик": (40, 90),
    "грузчик": (60, 100),
    "продавец": (50, 110),
}

@dp.message(Command("jobs"))
async def show_jobs(message: Message):
    msg = "🛠 Выбери профессию:\n"
    for job in jobs:
        msg += f"/job_{job} – {jobs[job][0]}–{jobs[job][1]} монет\n"
    await message.reply(msg)

for job in jobs:
    @dp.message(Command(f"job_{job}"))
    async def do_job(message: Message, job_name=job):
        await get_user(message.from_user.id, message.from_user.username or "noname")
        salary = random.randint(*jobs[job_name])
        await add_money(message.from_user.id, salary)
        await message.reply(f"Ты поработал как {job_name} и заработал {salary} монет!")

# === Монетка ===
@dp.message(Command("coin"))
async def coin_game(message: Message):
    args = message.text.split()
    if len(args) != 3:
        return await message.reply("Используй: /coin <ставка> <орел|решка>")

    try:
        bet = int(args[1])
        choice = args[2].lower()
        if choice not in ["орел", "решка"]:
            return await message.reply("Пиши 'орел' или 'решка'")

        balance = await get_balance(message.from_user.id)
        if bet > balance:
            return await message.reply("Недостаточно монет!")

        await remove_money(message.from_user.id, bet)
        result = random.choice(["орел", "решка"])

        if choice == result:
            win = bet * 2
            await add_money(message.from_user.id, win)
            await message.reply(f"Выпал {result.upper()}! Ты выиграл {win} монет 🎉")
        else:
            await message.reply(f"Выпал {result.upper()}! Ты проиграл 😢")

    except ValueError:
        await message.reply("Ставка должна быть числом!")

# === Магазин ===
items = [
    {"name": "😎 Крутая аватарка", "price": 100},
    {"name": "💎 VIP-рамка", "price": 250},
    {"name": "🔥 Плюшка мемов", "price": 500}
]

@dp.message(Command("shop"))
async def shop(message: Message):
    msg = "🛍 Магазин:\n"
    for i, item in enumerate(items, 1):
        msg += f"{i}. {item['name']} — {item['price']} монет\n"
    await message.reply(msg)

# === Рулетка ===
@dp.message(Command("daily"))
async def daily(message: Message):
    await get_user(message.from_user.id, message.from_user.username or "noname")
    last = await get_last_daily(message.from_user.id)
    now = datetime.now()

    if now - last < timedelta(hours=24):
        remaining = timedelta(hours=24) - (now - last)
        return await message.reply(f"🎁 Ты уже получал рулетку. Попробуй через {remaining.seconds // 3600}ч.")

    reward = random.choices(
        [0, 10, 50, 100, 500, 1000, 2000, 5000],
        weights=[20, 25, 20, 15, 10, 6, 3, 1],
        k=1
    )[0]

    await add_money(message.from_user.id, reward)
    await update_daily_time(message.from_user.id)
    await message.reply(f"🎁 Рулетка крутанулась! Тебе выпало: {reward} монет.")

# === Запуск ===
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())