import asyncio
import json
import logging
import os
import sqlite3
import datetime
import aiohttp
import base64
from pathlib import Path

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    LabeledPrice, PreCheckoutQuery, ContentType, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

# Загрузка переменных окружения (с проверкой)
load_dotenv()

# Критичные переменные
REQUIRED_ENV_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "YOOKASSA_PROVIDER_TOKEN",
    "SERVER_URL",
    "SERVER_PORT"
]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"❌ Missing required environment variables: {', '.join(missing_vars)}")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TelegramBot")

# Инициализация
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PAYMENT_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN")
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8080")  # Новый порт
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # ID администратора

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# Пути к файлам
QUESTIONS_DIR = Path("questions")
IMAGES_DIR = QUESTIONS_DIR / "images_oge_math"

# Состояния машины состояний
class TaskStates(StatesGroup):
    waiting_for_answer = State()
    payment_pending = State()

# Инициализация базы данных
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

# Вспомогательные функции
async def get_user(user_id: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

async def save_user(user_id: int, name: str, credits: int = 0):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO users (user_id, name, credits, last_activity)
    VALUES (?, ?, ?, datetime('now'))
    """, (user_id, name, credits))
    conn.commit()
    conn.close()

async def send_to_server(user_answer: str, image_url: str, student_id: int):
    """Отправка запроса на сервер для проверки ответа"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{SERVER_URL}:{SERVER_PORT}/check/",
                json={"user_answer": user_answer, "image_url": image_url, "student_id": student_id},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Серверный ошибка: {str(e)}")
            return {"is_correct": False, "explanation": f"Серверная ошибка: {str(e)}"}

# Обработчики команд
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await save_user(message.from_user.id, message.from_user.first_name)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📝 Решить задачу")],
            [KeyboardButton("📊 Моя статистика")],
            [KeyboardButton("🛠 Помощь")],
        ],
        resize_keyboard=True
    )
    
    await message.answer_reply(
        f"👋 Привет, {message.from_user.first_name}!\nЯ - твой умный репетитор по математике.",
        reply_markup=keyboard
    )

@dp.message(F.text == "📝 Решить задачу")
async def solve_task(message: types.Message, state: FSMContext):
    # Эмуляция получения задачи (в реальности нужно получить из базы)
    task = {
        "id": "oge_math_1",
        "text": "2 + 2 = ?",
        "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAhhPC/P3w+AAAAABJRU5ErkJggg=="
    }
    
    # Сохраняем состояние
    await state.set_data({"task_id": task["id"]})
    await state.update_data(task_data=task)
    
    # Отправка задачи
    await message.answer_photo(
        photo=FSInputFile(base64.b64decode(task["image"]), filename="task.png"),
        caption=f"📝 **Задача #{task['id']}**\n{task['text']}\n\nВведите ответ:"
    )
    
    # Переход в состояние ожидания ответа
    await state.set_state(TaskStates.waiting_for_answer)

@dp.message(TaskStates.waiting_for_answer)
async def check_answer(message: types.Message, state: FSMContext):
    user_answer = message.text
    task_data = await state.get_data()
    task_id = task_data.get("task_id")
    
    # Проверка ответа на сервере
    result = await send_to_server(
        user_answer=user_answer,
        image_url=task_data["task_data"]["image"],
        student_id=message.from_user.id
    )
    
    # Формирование ответа
    response_text = f"📋 **Ваш ответ**: `{user_answer}`\n\n"
    
    if result["is_correct"]:
        response_text += "🎉 **Правильно!**\n\n"
        response_text += "✅ **Объяснение**:\n" + result["explanation"]
    else:
        response_text += "❌ **Ошибка!**\n\n"
        response_text += "🔍 **Ваше решение**:\n" + result["explanation"]
    
    # Добавление кредитов за правильный ответ
    if result["is_correct"]:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET credits = credits + 1 WHERE user_id = ?",
            (message.from_user.id,)
        )
        conn.commit()
        conn.close()
        response_text += "\n\n💎 Вы получили +1 кредит за правильный ответ!"
    
    await message.answer(response_text)
    await state.clear()

@dp.message(F.text == "📊 Моя статистика")
async def user_stats(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("🤔 Вы еще не решали ни одной задачи!")
        return
    
    # В реальности тут будет запрос к базе с подробной статистикой
    stats = {
        "total_tasks": 15,
        "correct_answers": 12,
        "success_rate": 80.0,
        "weak_topics": ["Алгебра"],
        "credits": user[2] if user else 0
    }
    
    response_text = f"""
    📊 **Ваша статистика**:
    - Всего задач: {stats['total_tasks']}
    - Правильных ответов: {stats['correct_answers']}
    - Успеваемость: {stats['success_rate']}%
    - Кредитов: {stats['credits']}
    
    🔍 **Темы для работы**:
    - {', '.join(stats['weak_topics'])}
    """
    
    await message.answer(response_text)

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    """Сброс состояния бота (только для администратора)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас недостаточно прав для выполнения этой команды")
        return
    
    # Сброс состояния
    dp.storage.reset()
    await message.answer("✅ Состояние бота сброшено")

# Запуск бота
async def main():
    port = int(os.getenv("SERVER_PORT", "8002"))
    await dp.start_polling(bot, 
                          reset_webhook=True,
                          skip_updates=True,
                          port=port)

if __name__ == "__main__":
    logger.info(f"🌐 Запускаем Telegram бота на порту {SERVER_PORT}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен")

