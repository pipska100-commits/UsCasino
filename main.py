import asyncio
import random
import hashlib
import aiohttp
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Вставь сюда свой токен от CryptoPay
CRYPTO_PAY_TOKEN = "ВАШ_КРИПТО_ТОКЕН" 
CRYPTO_API_URL = "https://pay.crypt.bot/api"
MIN_BET = 1.0
# ============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

users = {}
invoices_seen = set()

# ================== HELPERS ==================

def get_user(uid):
    if uid not in users:
        users[uid] = {
            "balance": 0.0,
            "wager": 0.0,
            "server_seed": hashlib.sha256(str(random.random()).encode()).hexdigest()
        }
    return users[uid]

async def crypto_api(method, data=None):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{CRYPTO_API_URL}/{method}", json=data, headers=headers) as r:
                return await r.json()
        except Exception as e:
            logging.error(f"API Error: {e}")
            return {"ok": False}

# ================== START ==================

@dp.message(Command("start"))
async def start(msg: types.Message):
    get_user(msg.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="games")],
        [InlineKeyboardButton(text="💰 Профиль", callback_data="profile")]
    ])
    await msg.answer("🎰 *UsCasino*\nМинимальная ставка 1 USDT", parse_mode="Markdown", reply_markup=kb)

# ================== PROFILE ==================

@dp.callback_query(F.data == "profile")
async def profile(call: types.CallbackQuery):
    u = get_user(call.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Депозит", callback_data="deposit")],
        [InlineKeyboardButton(text="➖ Вывод", callback_data="withdraw")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="start_menu")]
    ])
    await call.message.edit_text(
        f"💰 Баланс: {u['balance']:.2f} USDT\n🎯 Оборот: {u['wager']:.2f}",
        reply_markup=kb
    )

@dp.callback_query(F.data == "start_menu")
async def back_to_start(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="games")],
        [InlineKeyboardButton(text="💰 Профиль", callback_data="profile")]
    ])
    await call.message.edit_text("🎰 *UsCasino*\nМинимальная ставка 1 USDT", parse_mode="Markdown", reply_markup=kb)

# ================== DEPOSIT ==================

@dp.callback_query(F.data == "deposit")
async def deposit(call: types.CallbackQuery):
    inv = await crypto_api("createInvoice", {
        "asset": "USDT",
        "amount": "10.0",
        "description": "UsCasino Deposit",
        "payload": str(call.from_user.id)
    })
    
    if inv.get("ok"):
        pay_url = inv['result']['pay_url']
        await call.message.answer(f"💳 Ссылка на оплату (10 USDT):\n{pay_url}")
    else:
        await call.message.answer("❌ Ошибка создания счета.")

async def check_invoices():
    while True:
        data = await crypto_api("getInvoices", {"status": "paid"})
        if data and data.get("ok"):
            for inv in data["result"]["items"]:
                inv_id = inv["invoice_id"]
                if inv_id not in invoices_seen:
                    invoices_seen.add(inv_id)
                    uid_str = inv.get("payload")
                    if uid_str and uid_str.isdigit():
                        uid = int(uid_str)
                        u = get_user(uid)
                        u["balance"] += float(inv["amount"])
                        logging.info(f"Зачислено {inv['amount']} пользователю {uid}")
                        try:
                            await bot.send_message(uid, f"✅ Баланс пополнен на {inv['amount']} USDT!")
                        except Exception as e:
                            logging.error(f"Error sending success message: {e}")
        await asyncio.sleep(10)

# ================== GAMES ==================

@dp.callback_query(F.data == "games")
async def games(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Dice", callback_data="dice_game")],
        [InlineKeyboardButton(text="🏀 Basket", callback_data="basket")],
        [InlineKeyboardButton(text="🎯 Darts", callback_data="darts")],
        [InlineKeyboardButton(text="⚽ Football", callback_data="football")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="start_menu")]
    ])
    await call.message.edit_text("🎮 Выберите игру:", reply_markup=kb)

@dp.callback_query(F.data == "basket")
async def basket(call: types.CallbackQuery): 
    await bot.send_dice(call.from_user.id, emoji="🏀")

@dp.callback_query(F.data == "darts")
async def darts(call: types.CallbackQuery): 
    await bot.send_dice(call.from_user.id, emoji="🎯")

@dp.callback_query(F.data == "football")
async def football(call: types.CallbackQuery): 
    await bot.send_dice(call.from_user.id, emoji="⚽")

# ================== RUN ==================

async def main():
    # Запуск фоновой задачи проверки платежей
    asyncio.create_task(check_invoices())
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
