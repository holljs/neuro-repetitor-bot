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

async def send_to_server(user_answer: str, image_url: str, task_text: str, student_id: int): # Добавили task_text
    """Отправка запроса на сервер для проверки ответа"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{SERVER_URL}:{SERVER_PORT}/check/",
                json={"user_answer": user_answer, "image_url": image_url, "task_text": task_text, "student_id": student_id},
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

# Сколько вопросов в одном тесте
TEST_LENGTH = 15 

@dp.message(F.text == "📝 Решить задачу")
async def solve_task(message: types.Message, state: FSMContext):
    if not ALL_TASKS:
        await message.answer("😕 База задач пуста.")
        return

    # Получаем текущие данные теста или создаем новые
    data = await state.get_data()
    current_question_num = data.get("current_question_num", 1)
    mistakes = data.get("mistakes", []) # Здесь будем копить ошибки
    score = data.get("score", 0)

    # 1. Выбираем случайную задачу
    task = random.choice(ALL_TASKS)
    task_id = task.get("id", "N/A")
    task_text = task.get("question", "")
    image_path_str = task.get("img")
    
    if not image_path_str:
        await message.answer("😕 Ошибка в структуре задачи. Попробуйте еще раз.")
        return

    image_path = Path(image_path_str)
    if not image_path.exists():
        await message.answer(f"😕 Не могу найти файл картинки: {image_path_str}")
        return

    # 2. Готовим картинку (Base64)
    with open(image_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    # 3. Сохраняем прогресс в состояние
    await state.set_data({
        "current_question_num": current_question_num,
        "mistakes": mistakes,
        "score": score,
        "current_task": {
            "task_id": task_id,
            "task_text": task_text,
            "image_base64": image_base64,
            "image_path": image_path_str # сохраняем путь для разбора ошибок
        }
    })

    # 4. Отправляем задачу пользователю
    photo = FSInputFile(image_path)
    await message.answer_photo(
        photo=photo,
        caption=f"📝 <b>Вопрос {current_question_num} из {TEST_LENGTH}</b>\n\n{task_text}\n\nВведите ваш ответ:"
    )
    
    await state.set_state(TaskStates.waiting_for_answer)

@dp.message(TaskStates.waiting_for_answer)
async def check_answer(message: types.Message, state: FSMContext):
    user_answer = message.text
    data = await state.get_data()
    
    current_task = data["current_task"]
    current_question_num = data["current_question_num"]
    mistakes = data["mistakes"]
    score = data["score"]

    loading_msg = await message.answer("🤔 Проверяю...")
    
    # Проверка ответа на сервере (Пока сервер отвечает по-старому, но мы берем только статус)
    result = await send_to_server(
        user_answer=user_answer,
        image_url=current_task["image_base64"],
        task_text=current_task["task_text"],
        student_id=message.from_user.id
    )
    await loading_msg.delete()

    # Формируем реакцию
    if result.get("is_correct", False):
        await message.answer("✅ <b>Верно!</b>")
        score += 1
        # Начисляем 1 кредит за верный ответ
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET credits = credits + 1 WHERE user_id = ?", (message.from_user.id,))
        conn.commit()
        conn.close()
    else:
        await message.answer("❌ <b>Неверно.</b> Запомнил твою ошибку.")
        # Сохраняем ошибку в копилку
        mistakes.append({
            "task": current_task,
            "user_answer": user_answer
        })

    # Увеличиваем счетчик вопросов
    current_question_num += 1

    # Решаем, что делать дальше: следующий вопрос или конец теста
    if current_question_num <= TEST_LENGTH:
        # Обновляем состояние и запускаем следующий вопрос
        await state.update_data(current_question_num=current_question_num, mistakes=mistakes, score=score)
        await solve_task(message, state) 
    else:
        # ТЕСТ ЗАВЕРШЕН
        result_text = f"🏁 <b>Тест завершен!</b>\n\nТвой результат: {score} из {TEST_LENGTH}.\nОшибок: {len(mistakes)}."
        
        if len(mistakes) > 0:
            # Показываем кнопку разбора
            builder = InlineKeyboardBuilder()
            builder.button(text="🧠 Разобрать ошибки", callback_data="start_review")
            await message.answer(result_text, reply_markup=builder.as_markup())
        else:
            await message.answer(result_text + "\n\nИдеально! Ты гений! 🎉")
            
        # Сбрасываем процесс теста, но оставляем mistakes в state data для коллбека разбора!
        await state.set_state(None) 
        await state.update_data(current_question_num=1, score=0)

# --- НОВЫЙ БЛОК: РАЗБОР ОШИБОК И ОБЪЯСНЕНИЯ ---

from aiogram import F
from aiogram.types import CallbackQuery

# Новая функция специально для запроса объяснений (чтобы не трогать старую send_to_server)
async def send_to_server_review(user_answer: str, image_url: str, task_text: str, student_id: int, simplify: bool = False):
    """Отправка запроса на сервер для ПОДРОБНОГО РАЗБОРА (или упрощения)"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{SERVER_URL}:{SERVER_PORT}/review/", # <--- Новый эндпоинт на сервере!
                json={
                    "user_answer": user_answer, 
                    "image_url": image_url, 
                    "task_text": task_text, 
                    "student_id": student_id,
                    "simplify": simplify # Флаг "объясни проще"
                },
                timeout=aiohttp.ClientTimeout(total=120) # Ждем дольше, т.к. ответ длинный
            ) as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Серверная ошибка (Review): {str(e)}")
            return {"explanation": f"Серверная ошибка: {str(e)}"}

@dp.callback_query(F.data == "start_review")
async def start_review_process(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mistakes = data.get("mistakes", [])
    
    if not mistakes:
        await callback.message.answer("Ошибок для разбора нет! Поздравляю! 🎉")
        await callback.answer()
        return

    await callback.message.answer("Начинаем разбор полетов! 🛠\nСейчас я подробно объясню каждую твою ошибку.")
    
    # Начинаем с первой ошибки (индекс 0)
    await state.update_data(current_review_index=0)
    await show_next_mistake_review(callback.message, state)
    await callback.answer()

async def show_next_mistake_review(message: types.Message, state: FSMContext):
    """Функция, которая достает ошибку и просит ИИ ее разобрать"""
    data = await state.get_data()
    mistakes = data.get("mistakes", [])
    idx = data.get("current_review_index", 0)
    
    if idx >= len(mistakes):
        await message.answer("Все ошибки разобраны! Ты молодец, что учишься на них. 💪\nЖми '📝 Решить задачу', чтобы начать новый тест.")
        # Очищаем ошибки после разбора
        await state.update_data(mistakes=[], current_review_index=0)
        return
        
    current_mistake = mistakes[idx]
    task_info = current_mistake["task"]
    user_answer = current_mistake["user_answer"]
    
    # Сообщаем ученику, какую задачу разбираем
    msg_text = f"❌ <b>Ошибка {idx + 1} из {len(mistakes)}</b>\n"
    msg_text += f"Твой неверный ответ: <code>{user_answer}</code>\n\n"
    msg_text += "⏳ Генерирую подробное объяснение..."
    
    # Отправляем фото задачи снова (чтобы ученик вспомнил условие)
    photo = FSInputFile(task_info["image_path"])
    loading_msg = await message.answer_photo(photo=photo, caption=msg_text)
    
    # --- ОТПРАВЛЯЕМ ЗАПРОС НА СЕРВЕР ЗА ОБЪЯСНЕНИЕМ ---
    result = await send_to_server_review(
        user_answer=user_answer,
        image_url=task_info["image_base64"],
        task_text=task_info["task_text"],
        student_id=message.from_user.id,
        simplify=False
    )
    
    await loading_msg.delete()
    
    # Формируем ответ с объяснением
    explanation_text = f"📚 <b>Подробный разбор:</b>\n{result.get('explanation', 'Нет объяснения.')}"
    
    # Делаем кнопки: "Дальше" и "Объясни проще"
    builder = InlineKeyboardBuilder()
    builder.button(text="Объясни проще 🍎", callback_data="simplify_review")
    builder.button(text="Следующая ошибка ➡️", callback_data="next_review")
    builder.adjust(1) # Кнопки одна под другой
    
    await message.answer(explanation_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "next_review")
async def process_next_review(callback: CallbackQuery, state: FSMContext):
    """Переход к следующей ошибке"""
    data = await state.get_data()
    idx = data.get("current_review_index", 0)
    
    # Увеличиваем индекс и показываем следующую ошибку
    await state.update_data(current_review_index=idx + 1)
    await show_next_mistake_review(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == "simplify_review")
async def process_simplify_review(callback: CallbackQuery, state: FSMContext):
    """Кнопка 'Объясни проще'"""
    data = await state.get_data()
    mistakes = data.get("mistakes", [])
    idx = data.get("current_review_index", 0)
    current_mistake = mistakes[idx]
    task_info = current_mistake["task"]
    user_answer = current_mistake["user_answer"]

    # Меняем кнопку на сообщение ожидания
    await callback.message.edit_reply_markup(reply_markup=None)
    loading_msg = await callback.message.answer("⏳ Прошу нейросеть объяснить проще (на яблоках)...")
    
    # Снова обращаемся к серверу, но с флагом simplify=True
    result = await send_to_server_review(
        user_answer=user_answer,
        image_url=task_info["image_base64"],
        task_text=task_info["task_text"],
        student_id=callback.from_user.id,
        simplify=True
    )
    
    await loading_msg.delete()
    
    explanation_text = f"🍎 <b>Объяснение для новичков:</b>\n{result.get('explanation', 'Нет объяснения.')}"
    
    # Возвращаем только кнопку "Следующая ошибка"
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующая ошибка ➡️", callback_data="next_review")
    await callback.message.answer(explanation_text, reply_markup=builder.as_markup())
    
    await callback.answer()

# -----------------------------------------------------------

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









