import asyncio
import json
import logging
import os
import sqlite3
import datetime
import aiohttp
from pathlib import Path

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, LabeledPrice, PreCheckoutQuery, ContentType, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

load_dotenv()

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
PAYMENT_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN")
SERVER_URL = "http://127.0.0.1:8002"
ADMIN_ID = 246254816

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

SUBJECT_NAMES = {
    "oge_math": "📐 Математика (ОГЭ)", "oge_physics": "⚛️ Физика (ОГЭ)", "oge_informatics": "💻 Информатика (ОГЭ)",
    "oge_russian": "🇷🇺 Русский язык (ОГЭ)", "oge_biology": "🧬 Биология (ОГЭ)", "oge_chemistry": "🧪 Химия (ОГЭ)",
    "oge_geography": "🌍 География (ОГЭ)", "oge_history": "📜 История (ОГЭ)", "oge_social": "⚖️ Обществознание (ОГЭ)",
    "oge_english": "🇬🇧 Английский (ОГЭ)", "oge_literature": "📚 Литература (ОГЭ)",
    "ege_math_profile": "📈 Математика (ЕГЭ Проф)", "ege_math_base": "📉 Математика (ЕГЭ База)",
    "ege_physics": "⚛️ Физика (ЕГЭ)", "ege_informatics": "💻 Информатика (ЕГЭ)", "ege_russian": "🇷🇺 Русский язык (ЕГЭ)",
    "ege_biology": "🧬 Биология (ЕГЭ)", "ege_chemistry": "🧪 Химия (ЕГЭ)", "ege_history": "📜 История (ЕГЭ)",
    "ege_social": "⚖️ Обществознание (ЕГЭ)", "ege_english": "🇬🇧 Английский (ЕГЭ)", "ege_literature": "📚 Литература (ЕГЭ)",
    "ege_geography": "🌍 География (ЕГЭ)"
}

REVERSE_SUBJECT_NAMES = {v: k for k, v in SUBJECT_NAMES.items()}

def init_db():
    with sqlite3.connect("users.db") as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER, subject TEXT, expiry_date TEXT, PRIMARY KEY (user_id, subject))")

def check_subscription(user_id, subject):
    if user_id == ADMIN_ID: return True, datetime.datetime(2099, 12, 31)
    with sqlite3.connect("users.db") as conn:
        row = conn.execute("SELECT expiry_date FROM subscriptions WHERE user_id = ? AND subject = ?", (user_id, subject)).fetchone()
        if row:
            expiry = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if expiry > datetime.datetime.now(): return True, expiry
    return False, None

def add_subscription(user_id, subject, days=30):
    now = datetime.datetime.now()
    _, current_expiry = check_subscription(user_id, subject)
    start_date = current_expiry if current_expiry and current_expiry > now else now
    new_expiry = start_date + datetime.timedelta(days=days)
    with sqlite3.connect("users.db") as conn:
        conn.execute("INSERT OR REPLACE INTO subscriptions (user_id, subject, expiry_date) VALUES (?, ?, ?)",
                     (user_id, subject, new_expiry.strftime("%Y-%m-%d %H:%M:%S")))
    return new_expiry

class TestState(StatesGroup):
    waiting_for_subject = State()
    answering_question = State()

def get_subjects_keyboard():
    if not os.path.exists("questions"): return None
    files = [f.replace(".json", "") for f in os.listdir("questions") if f.endswith(".json")]
    buttons = []
    for f in files:
        if os.path.getsize(f"questions/{f}.json") > 5:
            buttons.append(KeyboardButton(text=SUBJECT_NAMES.get(f, f)))
    if not buttons: return None
    buttons.sort(key=lambda x: x.text)
    return ReplyKeyboardMarkup(keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)], resize_keyboard=True)

async def ask_neuro_explain(question, correct, user_ans, solution=""):
    try:
        async with aiohttp.ClientSession() as session:
            # Передаем еще и официальное решение, чтобы нейросеть объясняла точно!
            payload = {"question": question, "correct_answer": correct, "user_answer": user_ans, "solution": solution}
            async with session.post(f"{SERVER_URL}/explain/", json=payload, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("explanation", "Ошибка нейросети.")
    except:
        pass
    return f"Правильный ответ: {correct}\n\nОфициальное решение:\n{solution}"

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    init_db()
    kb = get_subjects_keyboard()
    if not kb:
        await message.answer("⚠️ База вопросов пуста. Запустите парсер!")
        return
    await message.answer("👋 Привет! Выбери предмет для тренировки 👇", reply_markup=kb)
    await state.set_state(TestState.waiting_for_subject)

@dp.message(TestState.waiting_for_subject)
async def process_subject(message: types.Message, state: FSMContext):
    subject_code = REVERSE_SUBJECT_NAMES.get(message.text)
    if not subject_code or not os.path.exists(f"questions/{subject_code}.json"):
        await message.answer("❌ Неверный выбор.")
        return
        
    is_active, expiry = check_subscription(message.from_user.id, subject_code)
    
    if not is_active:
        await message.answer(f"🔒 Доступ к {message.text} стоит 200₽/мес.", reply_markup=ReplyKeyboardRemove())
        if PAYMENT_TOKEN:
            await bot.send_invoice(message.chat.id, title=f"Подписка: {message.text}", description="30 дней доступа",
                                   payload=subject_code, provider_token=PAYMENT_TOKEN, currency="RUB",
                                   prices=[LabeledPrice(label="Подписка", amount=20000)], start_parameter="sub")
        else:
            await message.answer("⚠️ Платежный токен не настроен.")
        return
        
    try:
        with open(f"questions/{subject_code}.json", "r", encoding="utf-8") as f:
            questions = json.load(f)
    except:
        await message.answer("❌ Ошибка файла вопросов.")
        return
        
    await message.answer(f"✅ Доступ активен до {expiry.strftime('%d.%m.%Y')}", reply_markup=ReplyKeyboardRemove())
    await state.update_data(questions=questions, current_index=0, score=0, subject=subject_code, mistakes=[])
    await show_question(message, state)

@dp.pre_checkout_query()
async def checkout(query: PreCheckoutQuery): 
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def got_payment(message: types.Message):
    sub = message.successful_payment.invoice_payload
    add_subscription(message.from_user.id, sub)
    await message.answer(f"🎉 Оплата прошла! Жми /start")

# --- ГЛАВНАЯ ФУНКЦИЯ ВЫВОДА ВОПРОСА ---
async def show_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    idx = data['current_index']
    questions = data['questions']
    
    # 1. Проверяем, не закончились ли вопросы
    if idx >= len(questions) or idx >= 15:
        score = data.get('score', 0)
        mistakes = data.get('mistakes', [])
        text = f"🏁 <b>Тест завершен!</b>\n\nТвой результат: {score} из {idx}."
        
        builder = InlineKeyboardBuilder()
        if mistakes:
            text += "\n\nЯ запомнил твои ошибки. Хочешь разобрать их с Нейросетью?"
            builder.add(types.InlineKeyboardButton(text="🧠 Разобрать ошибки", callback_data="start_explanation"))
            
        builder.add(types.InlineKeyboardButton(text="🏠 В меню", callback_data="go_menu"))
        builder.adjust(1)
        await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
        return

    # 2. Достаем текущий вопрос
    q = questions[idx]
    text = f"❓ <b>Вопрос {idx+1}</b>\n\n{q.get('question', '')}"
    img_path = q.get('img')

    # 3. Отправляем вопрос (с картинкой или без)
    try:
        if img_path:
            if str(img_path).startswith("http"):
                # Если это ссылка на интернет (старый парсер)
                await message.answer_photo(img_path, caption=text[:1000], parse_mode="HTML")
            else:
                # ЗАЩИТА ОТ БИТЫХ КАРТИНОК И ПУСТЫХ ФАЙЛОВ
                if os.path.exists(img_path) and os.path.getsize(img_path) > 100:
                    photo_file = FSInputFile(img_path)
                    await message.answer_photo(photo_file, caption=text[:1000], parse_mode="HTML")
                else:
                    await message.answer(text[:4096], parse_mode="HTML")
        else:
            # Если картинки нет
            await message.answer(text[:4096], parse_mode="HTML")
            
    except Exception as e:
        logging.error(f"Telegram не смог прожевать картинку: {e}")
        # Если Telegram выдал IMAGE_PROCESS_FAILED, отправляем просто текст
        await message.answer(text[:4096], parse_mode="HTML")

    await state.set_state(TestState.answering_question)

@dp.message(TestState.answering_question)
async def check_answer(message: types.Message, state: FSMContext):
    user_ans = message.text.strip().lower().replace(',', '.').replace(' ', '')
    data = await state.get_data()
    q = data['questions'][data['current_index']]
    correct = str(q['correct_answer']).strip().lower().replace(',', '.').replace(' ', '')
    mistakes = data.get('mistakes', [])
    new_score = data['score']
    
    if user_ans == correct:
        await message.answer("✅ Верно!")
        new_score += 1
    else:
        text = f"❌ Неверно.\nПравильный ответ: {q['correct_answer']}"
        await message.answer(text)
        mistakes.append({
            "question": q.get('question', ''),
            "correct_answer": q['correct_answer'],
            "user_answer": message.text,
            "solution": q.get('solution', '') # Запоминаем решение для нейросети!
        })
        
    await state.update_data(score=new_score, mistakes=mistakes, current_index=data['current_index'] + 1)
    await show_question(message, state)

@dp.callback_query(F.data == "start_explanation")
async def start_explanation(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mistakes = data.get('mistakes', [])
    
    if not mistakes:
        await callback_query.message.answer("Ошибок не найдено.")
        return
        
    await callback_query.message.answer("🤓 Нейросеть анализирует твои ошибки...")
    
    # Разбираем первые 3 ошибки
    for m in mistakes[:3]:
        explanation = await ask_neuro_explain(m['question'], m['correct_answer'], m['user_answer'], m.get('solution', ''))
        await callback_query.message.answer(f"❓ <b>Вопрос:</b> {m['question'][:100]}...\n\n💡 <b>Разбор:</b>\n{explanation}", parse_mode="HTML")
        await asyncio.sleep(1)
        
    await callback_query.message.answer("Разбор завершен! Жми /start")
    await state.clear()

@dp.callback_query(F.data == "go_menu")
async def go_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_start(callback_query.message, state)

async def main():
    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
