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
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    FSInputFile, CallbackQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Загрузка переменных окружения
load_dotenv()

# Критичные переменные
REQUIRED_ENV_VARS = ["BOT_TOKEN", "SERVER_URL", "SERVER_PORT"]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
    
# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelegramBot")

# Инициализация
API_TOKEN = os.getenv("BOT_TOKEN")
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1")
SERVER_PORT = os.getenv("SERVER_PORT", "8080")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Состояния машины состояний
class TaskStates(StatesGroup):
    choosing_subject = State()
    waiting_for_answer = State()

# Инициализация базы данных (пользователи)
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

# Вспомогательные функции работы с БД
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

# --- ВЗАИМОДЕЙСТВИЕ С СЕРВЕРОМ (API) ---

async def fetch_random_task(exam_type: str):
    """Получает случайную задачу от нашего FastAPI сервера"""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{SERVER_URL}:{SERVER_PORT}/random_task/?exam_type={exam_type}"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Ошибка получения задачи: {e}")
            return None

async def send_check_to_server(user_answer: str, task_id: str, student_id: int):
    """Отправка ответа на проверку (теперь серверу нужен только task_id и ответ)"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{SERVER_URL}:{SERVER_PORT}/check/",
                json={"user_answer": user_answer, "task_id": task_id, "student_id": student_id},
                timeout=60
            ) as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Серверная ошибка: {e}")
            return {"is_correct": False, "error": str(e)}

async def send_to_server_review(user_answer: str, image_url: str, task_text: str, student_id: int, simplify: bool = False):
    """Отправка запроса на сервер для разбора ошибок"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{SERVER_URL}:{SERVER_PORT}/review/",
                json={
                    "user_answer": user_answer, 
                    "image_url": image_url, 
                    "task_text": task_text, 
                    "student_id": student_id,
                    "simplify": simplify
                },
                timeout=120
            ) as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Серверная ошибка (Review): {e}")
            return {"explanation": f"Серверная ошибка: {str(e)}"}

# --- ОБРАБОТЧИКИ ТЕЛЕГРАМ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
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
        f"👋 Привет, {message.from_user.first_name}!\nЯ - твой Нейро-Репетитор. Подготовлю тебя к экзаменам на отлично!",
        reply_markup=keyboard
    )

TEST_LENGTH = 15 

@dp.message(F.text == "📝 Решить задачу")
async def choose_subject_menu(message: types.Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🧮 Математика", callback_data="subj_oge_math")
    builder.button(text="⚡ Физика", callback_data="subj_oge_physics")
    builder.button(text="🧪 Химия", callback_data="subj_oge_chemistry")
    builder.button(text="🇷🇺 Русский язык", callback_data="subj_oge_russian")
    builder.button(text="🇬🇧 Англ. язык", callback_data="subj_oge_english")
    builder.adjust(2) # По 2 кнопки в ряд
    
    await message.answer("📚 Выбери предмет для тренировки:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("subj_"))
async def start_test(callback: CallbackQuery, state: FSMContext):
    exam_type = callback.data.replace("subj_", "")
    await state.update_data(exam_type=exam_type, current_question_num=1, mistakes=[], score=0)
    
    await callback.message.delete()
    await send_next_task(callback.message, state)

async def send_next_task(message: types.Message, state: FSMContext):
    data = await state.get_data()
    exam_type = data.get("exam_type", "oge_math")
    current_question_num = data.get("current_question_num", 1)

    loading_msg = await message.answer("⏳ Подбираю интересную задачу...")
    
    # 1. Запрашиваем задачу у сервера
    task_data = await fetch_random_task(exam_type)
    await loading_msg.delete()
    
    if not task_data:
        await message.answer("😕 Не удалось получить задачу от сервера. Попробуй позже.")
        return

    task_id = task_data.get("id", "N/A")
    task_text = task_data.get("text", "Без текста")
    image_path_str = task_data.get("image", "")

    # 2. Готовим картинку (если она есть)
    image_base64 = None
    photo = None
    
    if image_path_str:
        image_path = Path(image_path_str)
        if image_path.exists():
            with open(image_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            photo = FSInputFile(image_path)

    # 3. Сохраняем данные для проверки ответа
    await state.update_data(current_task={
        "task_id": task_id,
        "task_text": task_text,
        "image_base64": image_base64,
        "image_path": image_path_str
    })

    # 4. Отправляем задачу пользователю
    msg_text = f"📝 <b>Вопрос {current_question_num} из {TEST_LENGTH}</b>\n\n{task_text}\n\n<i>Введите ваш ответ:</i>"
    
    if photo:
        await message.answer_photo(photo=photo, caption=msg_text)
    else:
        await message.answer(msg_text)
    
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
    
    # Отправляем ответ на проверку нашему серверу
    result = await send_check_to_server(
        user_answer=user_answer,
        task_id=current_task["task_id"],
        student_id=message.from_user.id
    )
    await loading_msg.delete()

    if result.get("is_correct", False):
        await message.answer("✅ <b>Верно!</b>")
        score += 1
        # Начисляем кредиты
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET credits = credits + 1 WHERE user_id = ?", (message.from_user.id,))
        conn.commit()
        conn.close()
    else:
        correct_ans = result.get('correct_was', 'Неизвестно')
        await message.answer(f"❌ <b>Неверно.</b> Запомнил твою ошибку!")
        mistakes.append({
            "task": current_task,
            "user_answer": user_answer
        })

    current_question_num += 1

    # Следующий вопрос или конец теста
    if current_question_num <= TEST_LENGTH:
        await state.update_data(current_question_num=current_question_num, mistakes=mistakes, score=score)
        # Так как send_next_task принимает message, передаем его
        await send_next_task(message, state) 
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

# --- РАЗБОР ОШИБОК ---

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
    await show_next_mistake_review(callback.message, state)
    await callback.answer()

async def show_next_mistake_review(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mistakes = data.get("mistakes", [])
    idx = data.get("current_review_index", 0)
    
    if idx >= len(mistakes):
        await message.answer("Все ошибки разобраны! 💪\nЖми '📝 Решить задачу', чтобы начать новый тест.")
        await state.update_data(mistakes=[], current_review_index=0)
        return
        
    current_mistake = mistakes[idx]
    task_info = current_mistake["task"]
    user_answer = current_mistake["user_answer"]
    
    msg_text = f"❌ <b>Ошибка {idx + 1} из {len(mistakes)}</b>\n"
    msg_text += f"Твой неверный ответ: <code>{user_answer}</code>\n\n⏳ Генерирую объяснение..."
    
    if task_info["image_path"] and Path(task_info["image_path"]).exists():
        photo = FSInputFile(task_info["image_path"])
        loading_msg = await message.answer_photo(photo=photo, caption=msg_text)
    else:
        loading_msg = await message.answer(msg_text)
    
    result = await send_to_server_review(
        user_answer=user_answer,
        image_url=task_info.get("image_base64"),
        task_text=task_info["task_text"],
        student_id=message.from_user.id,
        simplify=False
    )
    
    await loading_msg.delete()
    explanation_text = f"📚 <b>Подробный разбор:</b>\n{result.get('explanation', 'Нет объяснения.')}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Объясни проще 🍎", callback_data="simplify_review")
    builder.button(text="Следующая ошибка ➡️", callback_data="next_review")
    builder.adjust(1) 
    
    await message.answer(explanation_text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "next_review")
async def process_next_review(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("current_review_index", 0)
    await state.update_data(current_review_index=idx + 1)
    await show_next_mistake_review(callback.message, state)
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
    
    result = await send_to_server_review(
        user_answer=user_answer,
        image_url=task_info.get("image_base64"),
        task_text=task_info["task_text"],
        student_id=callback.from_user.id,
        simplify=True
    )
    
    await loading_msg.delete()
    explanation_text = f"🍎 <b>Объяснение для новичков:</b>\n{result.get('explanation', 'Нет объяснения.')}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Следующая ошибка ➡️", callback_data="next_review")
    await callback.message.answer(explanation_text, reply_markup=builder.as_markup())
    await callback.answer()

# --- СТАТИСТИКА И СБРОС ---

@dp.message(F.text == "📊 Моя статистика")
async def user_stats(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("🤔 Вы еще не решали ни одной задачи!")
        return
    
    response_text = f"📊 <b>Ваша статистика</b>:\n- Баланс кредитов: {user[2]}\n- Последняя активность: {user[3]}"
    await message.answer(response_text)

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас недостаточно прав")
        return
    await state.clear()
    await message.answer("✅ Состояние бота сброшено")

# --- ЗАПУСК ---

async def main():
    await dp.start_polling(bot, reset_webhook=True, skip_updates=True)

if __name__ == "__main__":
    logger.info(f"🌐 Запускаем Telegram бота. API: {SERVER_URL}:{SERVER_PORT}")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен")
