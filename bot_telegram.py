import asyncio
import json
import logging
import os
import random
import sqlite3
import datetime
import aiohttp
import base64
from pathlib import Path

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties  # <--- ДОБАВИЛИ ЭТУ СТРОКУ
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
    "BOT_TOKEN",         # <-- Ищем токен под тем именем, что у вас в .env
    "SERVER_URL",
    "SERVER_PORT"
    # Токен Юkassa пока убрали из обязательных, чтобы бот смог запуститься
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
API_TOKEN = os.getenv("BOT_TOKEN")                    # <-- Берем ваш BOT_TOKEN
PAYMENT_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN", "") # <-- Делаем необязательным
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8080") # Новый порт
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) # ID администратора

# Меняем инициализацию бота:
bot = Bot(
    token=API_TOKEN, 
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# Пути к файлам
QUESTIONS_DIR = Path("questions")
IMAGES_DIR = QUESTIONS_DIR / "images_oge_math"
DB_FILE = QUESTIONS_DIR / "oge_math.json" # <--- ДОБАВИЛИ

# Загружаем базу задач в память
try: # <--- ДОБАВИЛИ
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        ALL_TASKS = json.load(f)
    logger.info(f"✅ Успешно загружено {len(ALL_TASKS)} задач из {DB_FILE}")
except Exception as e:
    logger.error(f"❌ Не удалось загрузить базу задач: {e}")
    ALL_TASKS = []

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
            logger.error(f"Серверная ошибка: {str(e)}")
            return {"is_correct": False, "explanation": f"Серверная ошибка: {str(e)}"}

# Обработчики команд
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if not user:
        await save_user(message.from_user.id, message.from_user.first_name)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Решить задачу")],
            [KeyboardButton(text="📊 Моя статистика")],
            [KeyboardButton(text="🛠 Помощь")],
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\nЯ - твой умный репетитор по математике.",
        reply_markup=keyboard
    )

@dp.message(F.text == "📝 Решить задачу")
async def solve_task(message: types.Message, state: FSMContext):
    # --- Новая логика ---
    if not ALL_TASKS:
        await message.answer("😕 К сожалению, база задач пуста или не загрузилась. Обратитесь к администратору.")
        return
        
  # 1. Выбираем случайную задачу
    task = random.choice(ALL_TASKS)
    task_id = task.get("id", "N/A")
    task_text = task.get("question", "")      # <-- ДОЛЖНО БЫТЬ "question"
    image_path_str = task.get("img")          # <-- ДОЛЖНО БЫТЬ "img"
    
    if not image_path_str:
        await message.answer("😕 Ошибка в структуре задачи (нет файла картинки). Попробуйте еще раз.")
        return
        
    image_path = Path(image_path_str)         # <-- Берем путь целиком
    
    if not image_path.exists():
        await message.answer(f"😕 Не могу найти файл картинки: {image_path_str}. Попробуйте другую.")
        return
        
    # 2. Готовим картинку для отправки в LLaVA (Base64)
    with open(image_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        
    # 3. Сохраняем все нужные данные в состояние
    await state.set_data({
        "task_id": task_id,
        "image_base64": image_base64
    })
    
    # 4. Отправляем задачу пользователю
    photo = FSInputFile(image_path)
    await message.answer_photo(
        photo=photo,
        caption=f"📝 <b>Задача #{task_id}</b>\n\n{task_text}\n\nВведите ваш ответ:"
    )
    
    # 5. Переходим в состояние ожидания ответа
    await state.set_state(TaskStates.waiting_for_answer)

@dp.message(TaskStates.waiting_for_answer)
async def check_answer(message: types.Message, state: FSMContext):
    user_answer = message.text
    task_data = await state.get_data()
    task_id = task_data.get("task_id")
    
    # Проверка ответа на сервере
    result = await send_to_server(
        user_answer=user_answer,
        image_url=task_data.get("image_base64"),
        student_id=message.from_user.id
    )
    
    # Формирование ответа
    response_text = f"📋 <b>Ваш ответ</b>: <code>{user_answer}</code>\n\n"
    
    if result["is_correct"]:
        response_text += "🎉 <b>Правильно!</b>\n\n"
        response_text += "✅ <b>Объяснение</b>:\n" + result["explanation"]
        
        # Добавление кредитов за правильный ответ
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET credits = credits + 1 WHERE user_id = ?",
            (message.from_user.id,)
        )
        conn.commit()
        conn.close()
        response_text += "\n\n💎 Вы получили +1 кредит за правильный ответ!"
    else:
        response_text += "❌ <b>Ошибка!</b>\n\n"
        response_text += "🔍 <b>Решение</b>:\n" + result["explanation"]
    
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
    📊 <b>Ваша статистика</b>:
    - Всего задач: {stats['total_tasks']}
    - Правильных ответов: {stats['correct_answers']}
    - Успеваемость: {stats['success_rate']}%
    - Кредитов: {stats['credits']}
    
    🔍 <b>Темы для работы</b>:
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
    port = int(os.getenv("SERVER_PORT", "8080")) # Исправил порт по умолчанию на 8080
    await dp.start_polling(bot, 
                          reset_webhook=True,
                          skip_updates=True) # Убрал аргумент port, т.к. start_polling для aiogram 3 его не принимает

if __name__ == "__main__":
    logger.info(f"🌐 Запускаем Telegram бота. Сервер API ожидается на порту {SERVER_PORT}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен")




