import asyncio
import random
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "@your_admin_nick" # ЗАМЕНИ НА СВОЙ НИК
# ============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

users = {}
active_games = {}

def get_user(user: types.User):
    uid = user.id
    if uid not in users:
        users[uid] = {
            "balance": 10.0, # Стартовый баланс
            "wager": 0.0,
            "reg_date": datetime.now().strftime("%d.%m.%Y"),
            "games_count": 0
        }
    return users[uid]

# ================== КЛАВИАТУРЫ ==================

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="games_list")],
        [InlineKeyboardButton(text="💎 Профиль", callback_data="profile_view")]
    ])

def bet_selection_kb(game_type):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1$", callback_data=f"bet_{game_type}_1"),
         InlineKeyboardButton(text="2$", callback_data=f"bet_{game_type}_2")],
        [InlineKeyboardButton(text="5$", callback_data=f"bet_{game_type}_5"),
         InlineKeyboardButton(text="10$", callback_data=f"bet_{game_type}_10")],
        [InlineKeyboardButton(text="ALL IN", callback_data=f"bet_{game_type}_all")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="games_list")]
    ])

# ================== ПРОФИЛЬ И МЕНЮ ==================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user)
    await message.answer("🎰 UsCasino к вашим услугам!", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "profile_view")
async def view_profile(call: types.CallbackQuery):
    u = get_user(call.from_user)
    text = (f"💎 **Ваш профиль ›**\n"
            f" └ Текущий баланс: {u['balance']:.2f}$\n\n"
            f"Зарегистрирован: {u['reg_date']}\n"
            f" ├ Оборот: {u['wager']:.2f}$\n"
            f" 📥 Депозит 📤 **Вывод**")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Депозит", url=f"https://t.me/{ADMIN_USERNAME.replace('@','')}")],
        [InlineKeyboardButton(text="📤 Вывод", url=f"https://t.me/{ADMIN_USERNAME.replace('@','')}")],
        [InlineKeyboardButton(text="Назад ⬅️", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "main_menu")
async def back_to_main(call: types.CallbackQuery):
    await call.message.edit_text("🎰 **Главное меню казино:**", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "games_list")
async def list_games(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💣 МИНЫ (4x4)", callback_data="select_mines")],
        [InlineKeyboardButton(text="🎲 КОСТИ", callback_data="select_dice")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    await call.message.edit_text("🎮 **Выберите игру:**", reply_markup=kb)

@dp.callback_query(F.data.startswith("select_"))
async def select_bet(call: types.CallbackQuery):
    game = call.data.split("_")[1]
    await call.message.edit_text(f"💰 **Сумма ставки ({game.upper()}):**", reply_markup=bet_selection_kb(game))

# ================== ЛОГИКА МИН (4x4) ==================

def get_mines_kb(user_id):
    game = active_games[user_id]
    grid = []
    for r in range(4): # 4 ряда
        row = []
        for c in range(4): # 4 колонки
            idx = r * 4 + c
            if idx in game['opened']:
                # Если открыли бомбу или просто ячейку
                char = "💥" if idx in game['bombs'] else "🚩"
                row.append(InlineKeyboardButton(text=char, callback_data="ignore"))
            else:
                row.append(InlineKeyboardButton(text="❓", callback_data=f"mine_click_{idx}"))
        grid.append(row)
    
    grid.append([InlineKeyboardButton(text=f"💰 Забрать ({game['current_win']:.2f}$)", callback_data="mine_cashout")])
    return InlineKeyboardMarkup(inline_keyboard=grid)

@dp.callback_query(F.data.startswith("bet_mines_"))
async def start_mines(call: types.CallbackQuery):
    u = get_user(call.from_user)
    bet_val = call.data.split("_")[2]
    bet = u['balance'] if bet_val == "all" else float(bet_val)

    if u['balance'] < bet or bet <= 0:
        return await call.answer("❌ Мало денег!", show_alert=True)

    u['balance'] -= bet
    u['wager'] += bet
    
    # Генерируем 3 бомбы из 16 ячеек
    active_games[call.from_user.id] = {
        'bet': bet,
        'bombs': random.sample(range(16), 3),
        'opened': [],
        'current_win': 0.0
    }
    
    await call.message.edit_text(f"💣 **МИНЫ 4x4**\nСтавка: {bet:.2f}$\nНайди 🚩, не попади на 💥", 
                                 reply_markup=get_mines_kb(call.from_user.id))

@dp.callback_query(F.data.startswith("mine_click_"))
async def mine_click(call: types.CallbackQuery):
    uid = call.from_user.id
    if uid not in active_games: return
    
    idx = int(call.data.split("_")[2])
    game = active_games[uid]

    if idx in game['bombs']:
        # ВЗРЫВ
        game['opened'] = list(range(16)) # Показать все мины
        await call.message.edit_text(f"💥 **ВЗРЫВ!**\nВы проиграли {game['bet']:.2f}$", 
                                     reply_markup=get_mines_kb(uid))
        await asyncio.sleep(2)
        await call.message.answer("💀 Игра окончена. Попробуйте еще раз!", reply_markup=main_menu_kb())
        del active_games[uid]
    else:
        # УДАЧА
        if idx not in game['opened']:
            game['opened'].append(idx)
            game['current_win'] += 0.20
            await call.message.edit_reply_markup(reply_markup=get_mines_kb(uid))

@dp.callback_query(F.data == "mine_cashout")
async def mine_cashout(call: types.CallbackQuery):
    uid = call.from_user.id
    if uid not in active_games: return
    
    game = active_games[uid]
    u = get_user(call.from_user)
    
    u['balance'] += game['current_win']
    await call.message.edit_text(f"🎉 **Забрали!**\nВыигрыш: {game['current_win']:.2f}$\nБаланс: {u['balance']:.2f}$", 
                                 reply_markup=main_menu_kb())
    del active_games[uid]

# ================== DICE (ОСТАВЛЯЕМ ДЛЯ ВАРИАТИВНОСТИ) ==================

@dp.callback_query(F.data.startswith("bet_dice_"))
async def start_dice(call: types.CallbackQuery):
    u = get_user(call.from_user)
    bet_val = call.data.split("_")[2]
    bet = u['balance'] if bet_val == "all" else float(bet_val)

    if u['balance'] < bet: return await call.answer("❌ Баланс!")

    u['balance'] -= bet
    u['wager'] += bet
    msg = await call.message.answer_dice("🎲")
    
    await asyncio.sleep(3.5)
    if msg.dice.value >= 4:
        win = bet * 1.8
        u['balance'] += win
        res = f"✅ +{win:.2f}$"
    else:
        res = f"❌ -{bet:.2f}$"
    
    await call.message.answer(f"Результат: {msg.dice.value}\n{res}", reply_markup=main_menu_kb())

async def main():
    await dp.start_polling(bot)

if __nams__ == "__main__":
    asyncio.run(main())
