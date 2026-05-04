import asyncio
import json
import logging
import os
import sqlite3
import datetime
import aiohttp
import base64
import uuid
from pathlib import Path

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    FSInputFile, CallbackQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- ИМПОРТ ЮKASSA ---
from yookassa import Configuration, Payment

load_dotenv()

REQUIRED_ENV_VARS = ["BOT_TOKEN", "SERVER_URL", "SERVER_PORT", "YOOKASSA_SHOP_ID", "YOOKASSA_SECRET_KEY"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"❌ Не хватает переменных в .env: {', '.join(missing_vars)}")
    
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelegramBot")

API_TOKEN = os.getenv("BOT_TOKEN")
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8080")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
INTERNAL_TOKEN = os.getenv("INTERNAL_BOT_TOKEN", "tg-super-secret-password-2026-xyz")

# Настройка ЮКассы напрямую в боте
Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

# --- НАСТРОЙКА ПРОКСИ (Туннель через Германию) ---
from aiogram.client.session.aiohttp import AiohttpSession

proxy_url = "http://T0khVpu1Dy53:PX1@196.19.11.81:8000"
session = AiohttpSession(proxy=proxy_url)

# Инициализация бота через прокси
bot = Bot(
    token=API_TOKEN, 
    session=session, 
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

class TaskStates(StatesGroup):
    choosing_subject = State()
    waiting_for_answer = State()

class PaymentProcess(StatesGroup):
    waiting_for_check = State()

# --- НЕЗАВИСИМАЯ БАЗА ТЕЛЕГРАМА ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        credits INTEGER DEFAULT 0,
        last_activity TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_db()

async def get_user(user_id: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

async def save_user(user_id: int, name: str):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, name, credits, last_activity) VALUES (?, ?, ?, datetime('now'))", (user_id, name, 16))
    else:
        cursor.execute("UPDATE users SET name=?, last_activity=datetime('now') WHERE user_id=?", (name, user_id))
    conn.commit()
    conn.close()

async def deduct_credits(user_id: int, amount: int):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user or user[0] < amount:
        conn.close()
        return False
    cursor.execute("UPDATE users SET credits = credits - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

async def add_credits(user_id: int, amount: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- ВЗАИМОДЕЙСТВИЕ С СЕРВЕРОМ ---
async def fetch_random_task(exam_type: str, student_id: int):
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{SERVER_URL}:{SERVER_PORT}/random_task/?exam_type={exam_type}&student_id={student_id}&vk_params={INTERNAL_TOKEN}"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            return None

async def send_check_to_server(user_answer: str, task_id: str, student_id: int):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{SERVER_URL}:{SERVER_PORT}/check/",
                json={"user_answer": user_answer, "task_id": task_id, "student_id": str(student_id), "vk_params": INTERNAL_TOKEN},
                timeout=60
            ) as response:
                return await response.json()
        except Exception as e:
            return {"is_correct": False, "error": str(e)}

async def send_to_server_review(user_answer: str, image_url: str, task_text: str, student_id: int, simplify: bool = False):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{SERVER_URL}:{SERVER_PORT}/review/",
                json={"user_answer": user_answer, "image_url": image_url, "task_text": task_text, "student_id": str(student_id), "simplify": simplify, "vk_params": INTERNAL_TOKEN},
                timeout=120
            ) as response:
                return await response.json()
        except Exception as e:
            return {"explanation": f"Серверная ошибка: {str(e)}"}

# --- ОБРАБОТЧИКИ ТЕЛЕГРАМ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await save_user(message.from_user.id, message.from_user.first_name)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Решить задачу")],
            [KeyboardButton(text="📊 Моя статистика"), KeyboardButton(text="💳 Пополнить баланс")],
            [KeyboardButton(text="🛠 Помощь")],
        ], resize_keyboard=True
    )
    await message.answer(f"👋 Привет, {message.from_user.first_name}!\nЯ - твой Нейро-Репетитор. Подготовлю тебя к экзаменам на отлично!", reply_markup=keyboard)

TEST_LENGTH = 15 

@dp.message(F.text == "📝 Решить задачу")
async def choose_subject_menu(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🧮 Математика", callback_data="subj_oge_math")
    builder.button(text="🇷🇺 Русский язык", callback_data="subj_oge_russian")
    builder.button(text="⚡ Физика", callback_data="subj_oge_physics")
    builder.button(text="🧪 Химия", callback_data="subj_oge_chemistry")
    builder.button(text="🇬🇧 Англ. язык", callback_data="subj_oge_english")
    builder.button(text="🌍 География", callback_data="subj_oge_geography")
    builder.button(text="🧬 Биология", callback_data="subj_oge_biology")
    builder.button(text="💻 Информатика", callback_data="subj_oge_informatics")
    builder.button(text="📜 История", callback_data="subj_oge_history")
    builder.button(text="📊 Обществозн.", callback_data="subj_oge_social")
    builder.button(text="💻 Информатика ЕГЭ", callback_data="subj_inf_ege")
    builder.button(text="🌍 География ЕГЭ", callback_data="subj_geo_ege")
    builder.button(text="🇬🇧 Англ. ЕГЭ", callback_data="subj_ege_english")
    builder.button(text="🧪 Химия ЕГЭ", callback_data="subj_chem_ege")
    builder.adjust(2)
    await message.answer("📚 Выбери предмет для тренировки:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("subj_"))
async def choose_tariff_menu(callback: CallbackQuery, state: FSMContext):
    exam_type = callback.data.replace("subj_", "")
    await state.update_data(exam_type=exam_type)
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Стандарт (3 кр.)", callback_data="tariff_standard")
    builder.button(text="🔥 Профи (4 кр.)", callback_data="tariff_pro")
    builder.adjust(1)
    await callback.message.edit_text("Выбери формат тренировки:\n\n<b>🟢 Стандарт (3 кредита)</b> — обычные разборы ошибок.\n<b>🔥 Профи (4 кредита)</b> — разборы ошибок максимально просто, 'на пальцах'.", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("tariff_"))
async def start_test(callback: CallbackQuery, state: FSMContext):
    test_mode = callback.data.replace("tariff_", "")
    cost = 4 if test_mode == "pro" else 3
    success = await deduct_credits(callback.fromuser.id, cost)
    if not success:
        await callback.answer("❌ На балансе недостаточно кредитов! Пополните баланс.", show_alert=True)
        return
    await state.update_data(test_mode=test_mode, current_question_num=1, mistakes=[], score=0)
    await callback.message.delete()
    await send_next_task(callback.message, state, callback.from_user.id)

async def send_next_task(message: types.Message, state: FSMContext, user_id: int):
    data = await state.get_data()
    exam_type = data.get("exam_type", "oge_math")
    current_question_num = data.get("current_question_num", 1)
    loading_msg = await bot.send_message(user_id, "⏳ Подбираю интересную задачу...")
    task_data = await fetch_random_task(exam_type, user_id)
    await loading_msg.delete()
    if not task_data:
        await bot.send_message(user_id, "😕 Не удалось получить задачу от сервера. Попробуй позже.")
        return
    if task_data.get("done"):
        await bot.send_message(user_id, task_data.get("text", "Все задачи решены!"))
        await state.set_state(None)
        return

    task_id = task_data.get("id", "N/A")
    task_text = task_data.get("text", "Без текста")
    image_path_str = task_data.get("image", "")
    image_base64 = None
    photo = None
    if image_path_str:
        image_path = Path(image_path_str)
        if image_path.exists():
            with open(image_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            photo = FSInputFile(image_path)

    await state.update_data(current_task={"task_id": task_id, "task_text": task_text, "image_base64": image_base64, "image_path": image_path_str})
    msg_text = f"📝 <b>Вопрос {current_question_num} из {TEST_LENGTH}</b>\n\n{task_text}\n\n<i>Введите ваш ответ:</i>"
    if photo: await bot.send_photo(chat_id=user_id, photo=photo, caption=msg_text)
    else: await bot.send_message(chat_id=user_id, text=msg_text)
    await state.set_state(TaskStates.waiting_for_answer)

@dp.message(TaskStates.waiting_for_answer)
async def process_answer(message: types.Message, state: FSMContext):
    user_answer = message.text
    data = await state.get_data()
    current_task = data["current_task"]
    current_question_num = data["current_question_num"]
    mistakes = data["mistakes"]
    score = data["score"]
    loading_msg = await message.answer("🤔 Проверяю...")
    result = await send_check_to_server(user_answer=user_answer, task_id=current_task["task_id"], student_id=message.from_user.id)
    await loading_msg.delete()
    if result.get("is_correct", False):
        await message.answer("✅ <b>Верно!</b>")
        score += 1
    else:
        await message.answer(f"❌ <b>Неверно.</b> Запомнил твою ошибку!")
        mistakes.append({"task": current_task, "user_answer": user_answer})
    current_question_num += 1
    if current_question_num <= TEST_LENGTH:
        await state.update_data(current_question_num=current_question_num, mistakes=mistakes, score=score)
        await send_next_task(message, state, message.from_user.id) 
    else:
        result_text = f"🏁 <b>Тест завершен!</b>\n\nТвой результат: {score} из {TEST_LENGTH}.\nОшибок: {len(mistakes)}."
        if len(mistakes) > 0:
            builder = InlineKeyboardBuilder()
            builder.button(text="🧠 Разобрать ошибки", callback_data="start_review")
            await message.answer(result_text, reply_markup=builder.as_markup())
        else:
            await message.answer(result_text + "\n\nИдеально! Ты гений! 🎉")
        await state.set_state(None) 
        await state.update_data(current_question_num=1, score=0)

@dp.callback_query(F.data == "start_review")
async def start_review_process(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mistakes = data.get("mistakes", [])
    if not mistakes:
        await callback.message.answer("Ошибок для разбора нет! 🎉")
        await callback.answer()
        return
    await callback.message.answer("Начинаем разбор полетов! 🛠\nСейчас нейросеть объяснит каждую твою ошибку.")
    await state.update_data(current_review_index=0)
    await show_next_mistake_review(callback.message, state, callback.from_user.id)
    await callback.answer()

async def show_next_mistake_review(message: types.Message, state: FSMContext, user_id: int):
    data = await state.get_data()
    mistakes = data.get("mistakes", [])
    idx = data.get("current_review_index", 0)
    test_mode = data.get("test_mode", "standard")
    if idx >= len(mistakes):
        await bot.send_message(user_id, "Все ошибки разобраны! 💪\nЖми '📝 Решить задачу', чтобы начать новый тест.")
        await state.update_data(mistakes=[], current_review_index=0)
        return
    current_mistake = mistakes[idx]
    task_info = current_mistake["task"]
    user_answer = current_mistake["user_answer"]
    msg_text = f"❌ <b>Ошибка {idx + 1} из {len(mistakes)}</b>\nТвой неверный ответ: <code>{user_answer}</code>\n\n⏳ Генерирую объяснение..."
    if task_info["image_path"] and Path(task_info["image_path"]).exists():
        photo = FSInputFile(task_info["image_path"])
        loading_msg = await bot.send_photo(chat_id=user_id, photo=photo, caption=msg_text)
    else:
        loading_msg = await bot.send_message(chat_id=user_id, text=msg_text)
    result = await send_to_server_review(user_answer=user_answer, image_url=task_info.get("image_base64"), task_text=task_info["task_text"], student_id=user_id, simplify=False)
    await loading_msg.delete()
    explanation_text = f"📚 <b>Подробный разбор:</b>\n{result.get('explanation', 'Нет объяснения.')}"
    builder = InlineKeyboardBuilder()
    if test_mode == "pro": builder.button(text="Объясни проще 🍎", callback_data="simplify_review")
    builder.button(text="Следующая ошибка ➡️", callback_data="next_review")
    builder.adjust(1) 
    await bot.send_message(chat_id=user_id, text=explanation_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "next_review")
async def process_next_review(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("current_review_index", 0)
    await state.update_data(current_review_index=idx + 1)
    await show_next_mistake_review(callback.message, state, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data == "simplify_review")
async def process_simplify_review(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mistakes = data.get("mistakes", [])
    idx = data.get("current_review_index", 0)
    current_mistake = mistakes[idx]
    task_info = current_mistake["task"]
    user_answer = current_mistake["user_answer"]
    await callback.message.edit_reply_markup(reply_markup=None)
    loading_msg = await callback.message.answer("⏳ Прошу нейросеть объяснить проще (на яблоках)...")
    result = await send_to_server_review(user_answer=user_answer, image_url=task_info.get("image_base64"), task_text=task_info["task_text"], student_id=callback.from_user.id, simplify=True)
    await loading_msg.delete()
    explanation_text = f"🍎 <b>Объяснение для новичков:</b>\n{result.get('explanation', 'Нет объяснения.')}"
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующая ошибка ➡️", callback_data="next_review")
    await callback.message.answer(explanation_text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.message(F.text == "📊 Моя статистика")
async def user_stats(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("🤔 Вы еще не решали ни одной задачи!")
        return
    await message.answer(f"📊 <b>Ваша статистика</b>:\n- Баланс кредитов: <b>{user[2]}</b> кр.\n- Последняя активность: {user[3]}")

# --- ОПЛАТА ССЫЛКАМИ ---
@dp.message(F.text == "💳 Пополнить баланс")
async def cmd_buy_menu(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="Пакет 'Минимум' (15 кр.) — 150 руб.", callback_data="buy_15_150")
    builder.button(text="Пакет 'Максимум' (100 кр.) — 700 руб.", callback_data="buy_100_700")
    builder.adjust(1)
    await message.answer("Выберите пакет для пополнения:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def create_payment_link(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    credits_to_add = int(parts[1])
    price = float(parts[2])
    
    try:
        # Генерируем ссылку в ЮКассе
        payment = Payment.create({
            "amount": {"value": "%.2f" % price, "currency": "RUB"}, 
            "confirmation": {"type": "redirect", "return_url": f"https://t.me/{(await bot.get_me()).username}"}, 
            "capture": True, 
            "description": f"Покупка {credits_to_add} кредитов (Нейро-Репетитор)"
        }, uuid.uuid4())
        
        await state.update_data(payment_id=payment.id, credits_to_add=credits_to_add)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="➡️ Перейти к оплате", url=payment.confirmation.confirmation_url)
        builder.button(text="✅ Я оплатил(а)", callback_data="check_payment")
        
        await callback.message.edit_text(f"Счет на *{int(price)} руб.* создан.\n\nНажмите кнопку ниже для оплаты, а затем возвращайтесь сюда и нажмите «Я оплатил(а)».", reply_markup=builder.as_markup())
        await state.set_state(PaymentProcess.waiting_for_check)
    except Exception as e:
        logger.error(f"Ошибка ЮКассы: {e}")
        await callback.answer("Ошибка создания платежа.", show_alert=True)
    await callback.answer()

@dp.callback_query(F.data == "check_payment", PaymentProcess.waiting_for_check)
async def check_payment_status(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    payment_id = user_data.get("payment_id")
    credits_to_add = user_data.get("credits_to_add")
    
    if not payment_id: return
    try:
        payment_info = Payment.find_one(payment_id)
        if payment_info.status == "succeeded":
            await add_credits(callback.from_user.id, credits_to_add)
            user = await get_user(callback.from_user.id)
            new_balance = user[2] if user else credits_to_add
            
            await callback.message.edit_text(f"✅ Оплата прошла успешно!\nНачислено: *{credits_to_add}* кредитов.\nВаш новый баланс: *{new_balance}* кр.")
            await state.clear()
        elif payment_info.status == "pending": 
            await callback.answer("Платёж ещё обрабатывается. Проверьте чуть позже.", show_alert=True)
        else: 
            await callback.message.edit_text("❌ Платёж отменен или истек срок действия.", reply_markup=None)
            await state.clear()
    except Exception as e:
        logger.error(f"Ошибка проверки: {e}")
        await callback.answer("Ошибка проверки. Попробуйте позже.", show_alert=True)

# --- АДМИНКА ---
@dp.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("✅ Состояние бота сброшено")

@dp.message(Command("give"))
async def cmd_give(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        args = message.text.split()
        target_id, amount = int(args[1]), int(args[2])
        await add_credits(target_id, amount)
        await message.answer(f"✅ Успешно! Начислено {amount} кр. пользователю {target_id}")
        await bot.send_message(target_id, f"🎁 <b>Подарок от администратора!</b>\nНа ваш баланс зачислено: {amount} кр.")
    except Exception: await message.answer("❌ Ошибка. Правильный формат:\n`/give 123456789 50`")

async def main():
    await dp.start_polling(bot, reset_webhook=True, skip_updates=True)

if __name__ == "__main__":
    logger.info(f"🌐 Запускаем Telegram бота. Оплата через ссылки ЮКассы.")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен")
