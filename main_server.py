import os
import logging
import random
import json
import re
import sqlite3
import aiohttp  
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# --- ИНИЦИАЛИЗАЦИЯ ---
load_dotenv()
app = FastAPI(title="Neuro Repetitor API", version="2.1.0")

# --- СЛОВАРЬ ТЕМ ---
TOPIC_NAMES = {
    "topic_01": "🏠 Практические задачи", "topic_02": "🔢 Вычисления и дроби",
    "topic_03": "📏 Единицы измерения", "topic_04": "⚖️ Уравнения",
    "topic_04_eq": "⚖️ Уравнения", "topic_05": "📍 Координатная прямая",
    "topic_06": "📊 Графики и диаграммы", "topic_07": "📈 Графики функций",
    "topic_08": "🧩 Выражения", "topic_09": "🧪 Формулы", "topic_10": "🔢 Последовательности",
    "grammar": "📚 Грамматика (Англ)", "vocabulary": "📝 Лексика (Англ)",
    "syntax": "🏗️ Синтаксис", "punctuation": "✍️ Пунктуация",
    "orthography": "📝 Орфография", "lexis": "📖 Лексика и грамматика",
    "chemistry_part1": "🧪 Химия (Часть 1)", "physics_part1": "⚡ Физика (Часть 1)",
    "geography_part1": "🌍 География (Часть 1)",
    "biology_part1": "🧬 Биология",
    "informatics_part1": "💻 Информатика",
    "history_part1": "📜 История",
    "social_part1": "📊 Обществознание",
    "informatics_ege": "💻 Информатика ЕГЭ",
    "geography_ege": "🌍 География ЕГЭ"
}

if Path("questions").exists():
    app.mount("/questions", StaticFiles(directory="questions"), name="questions")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NeuroRepetitor")

# --- ФУНКЦИЯ ДЛЯ РАССЫЛКИ ВК ---
async def send_vk_message(user_id: str, message: str):
    """Отправляет сообщение пользователю ВК от имени группы"""
    vk_token = os.getenv("VK_TOKEN")
    if not vk_token:
        logger.error("❌ VK_TOKEN не найден в .env")
        return False
        
    url = "https://api.vk.com/method/messages.send"
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": random.randint(1, 2147483647),
        "v": "5.131",
        "access_token": vk_token
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=params) as resp:
                result = await resp.json()
                if "error" in result:
                    logger.error(f"❌ Ошибка отправки ВК: {result['error']['error_msg']}")
                    return False
                return True
    except Exception as e:
        logger.error(f"❌ Ошибка соединения с ВК: {e}")
        return False

# --- БАЗЫ ДАННЫХ ВОПРОСОВ ---
QUESTIONS_DIR = Path("questions")
PROGRESS_FILE = Path("user_progress.json")
DATABASES = {
    "oge_math": [], "oge_english": [], "oge_russian": [], 
    "oge_chemistry": [], "oge_physics": [], "oge_geography": [],
    "oge_biology": [], "oge_informatics": [], "oge_history": [], "oge_social": [],
    "math_ege": [], "russian_ege": []
}

def load_database(filename, db_key):
    filepath = QUESTIONS_DIR / filename
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f: DATABASES[db_key] = json.load(f)
            logger.info(f"✅ База {db_key} загружена: {len(DATABASES[db_key])} шт.")
        except Exception as e: logger.error(f"❌ Ошибка: {e}")

load_database("oge_math.json", "oge_math")
load_database("oge_english.json", "oge_english")
load_database("oge_russian.json", "oge_russian")
load_database("oge_chemistry.json", "oge_chemistry")
load_database("oge_physics.json", "oge_physics")
load_database("oge_geography.json", "oge_geography")
# --- НОВЫЕ ПРЕДМЕТЫ ---
load_database("oge_biology.json", "oge_biology")
load_database("oge_informatics.json", "oge_informatics")
load_database("oge_history.json", "oge_history")
load_database("oge_social.json", "oge_social")
load_database("math_ege.json", "math_ege")
load_database("russian_ege.json", "russian_ege")
load_database("inf_ege.json", "inf_ege")
load_database("geo_ege.json", "geo_ege")
# --- БАЗА ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ (ВК ЭКОНОМИКА) ---
def init_vk_db():
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        credits INTEGER DEFAULT 0,
        last_activity TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_vk_db()

def init_vk_user(user_id: str) -> int:
    """Проверяет юзера. Если новый - дает 5 кредитов. Возвращает текущий баланс."""
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("INSERT INTO users (user_id, credits, last_activity) VALUES (?, ?, datetime('now'))", (user_id, 5))
        conn.commit()
        balance = 5
    else:
        cursor.execute("UPDATE users SET last_activity=datetime('now') WHERE user_id=?", (user_id,))
        conn.commit()
        balance = user[0]
    conn.close()
    return balance

def change_vk_credits(user_id: str, amount: int) -> int:
    """Изменяет баланс (списание или начисление)"""
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    new_balance = cursor.fetchone()[0]
    conn.close()
    return new_balance

# --- ЛОГИКА АНТИ-ПОВТОРА ---
def get_user_progress(user_id: str):
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(user_id), [])
    return []

def save_user_progress(user_id: str, task_id: str):
    data = {}
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f: data = json.load(f)
    uid = str(user_id)
    if uid not in data: data[uid] = []
    if task_id not in data[uid]:
        data[uid].append(task_id)
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def check_student_answer(student_ans, correct_ans):
    """Умная проверка ответа для всех предметов (Математика, История, Общество и т.д.)"""
    if not student_ans or not correct_ans: return False
    
    # 1. Приводим всё к верхнему регистру
    student_ans = str(student_ans).upper()
    correct_ans = str(correct_ans).upper()

    # 2. ОГЭ История/Биология: Правильный ответ состоит ТОЛЬКО из цифр ("531", "12")
    if correct_ans.isdigit():
        # Ученик написал "А-5, Б-3". Вытаскиваем только цифры:
        clean_student = re.sub(r'\D', '', student_ans)
        return clean_student == correct_ans
    
    # 3. ОГЭ Математика/Физика: Ответ с минусом или дроби ("-3.5", "0,2")
    elif correct_ans.replace('.', '').replace(',', '').replace('-', '').isdigit():
        # Оставляем минусы и точки, просто убираем пробелы
        s_ans = student_ans.replace(" ", "").replace(",", ".")
        c_ans = correct_ans.replace(" ", "").replace(",", ".")
        return s_ans == c_ans
        
    # 4. Общество/Биология: Текстовый ответ (буквы "АБГЕ", слова "МОНАРХИЯ")
    else:
        # Выкидываем все пробелы, точки, запятые, дефисы
        clean_student = re.sub(r'[\s\-\.,;:]', '', student_ans)
        clean_correct = re.sub(r'[\s\-\.,;:]', '', correct_ans)
        return clean_student == clean_correct

# --- МОДЕЛИ ДАННЫХ ---
class CheckRequest(BaseModel):
    user_answer: str
    task_id: str  
    student_id: Optional[str] = None

class ReviewRequest(BaseModel):
    user_answer: str
    image_url: Optional[str] = None
    task_text: Optional[str] = None
    student_id: Optional[str] = None
    simplify: bool = False

class PaymentRequest(BaseModel):
    student_id: Optional[str] = None
    task_id: Optional[str] = None
    test_mode: str = "standard"

# --- МАРШРУТЫ ---

@app.post("/start_test_payment/")
async def pay_for_test(request: PaymentRequest):
    student_id = str(request.student_id)
    test_mode = request.test_mode
    ADMIN_IDS = ["54451631", "12345678"] 
    
    cost = 4 if test_mode == "pro" else 3
    
    # Админам всё бесплатно
    if student_id in ADMIN_IDS:
        return {"success": True, "new_balance": "unlimited", "cost": 0}
    
    # 1. Проверяем юзера и выдаем 5 приветственных кредитов, если он новый
    current_balance = init_vk_user(student_id)
    
    # 2. Проверяем, хватает ли баланса
    if current_balance < cost:
        return {"success": False, "new_balance": current_balance, "cost": cost, "error": "Недостаточно кредитов"}
        
    # 3. Списываем кредиты
    new_balance = change_vk_credits(student_id, -cost)
    
    return {"success": True, "new_balance": new_balance, "cost": cost}

@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge_math", student_id: str = "guest"):
    db = DATABASES.get(exam_type, [])
    if not db: raise HTTPException(status_code=500, detail="База пуста")
    
    solved_ids = get_user_progress(student_id)
    available_tasks = [t for t in db if str(t.get("id")) not in solved_ids]
    
    if not available_tasks:
        return {"id": "done", "topic": "done", "text": "🎉 Все задачи решены!", "image": "", "answer": "---", "done": True}
    
    task = random.choice(available_tasks)
    img_path = task.get("image", "")
    
    if img_path and not img_path.startswith("http"):
        # Если в JSON путь уже начинается с questions/, отдаем его как есть
        if img_path.startswith("questions/"):
            pass 
        else:
            # Старая логика для других предметов
            clean_name = img_path.split('/')[-1]
            if exam_type == "oge_physics": img_path = f"questions/images_oge_physics/{clean_name}"
            elif exam_type == "oge_chemistry": img_path = f"questions/images_oge_chemistry/{clean_name}"
            elif exam_type == "oge_geography": img_path = f"questions/images_oge_geography/{clean_name}"
            elif exam_type == "math_ege": img_path = f"questions/images_ege_math/{clean_name}" # Путь для ЕГЭ Математики
            else: 
                topic = task.get("topic", "topic_01")
                img_path = f"questions/images_oge_math/{topic}/{clean_name}"

    return {"id": task.get("id", "unknown"), "topic": task.get("topic", "Общая тема"), "text": task.get("task_text", task.get("text", "")), "image": img_path, "answer": task.get("answer", "")}

@app.post("/check/")
async def check_answer_smart(request: CheckRequest):
    task = next((t for db in DATABASES.values() for t in db if str(t.get("id")) == str(request.task_id)), None)
    if not task: return {"is_correct": False, "error": "Задача не найдена"}

    correct_answer = str(task.get("answer", ""))
    is_correct = check_student_answer(request.user_answer, correct_answer)
    
    if not is_correct and correct_answer != "---":
        try:
            prompt = f"Равны ли ответы: '{correct_answer}' и '{request.user_answer}'? Верни строго JSON: {{\"is_correct\": true/false}}"
            output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
            is_correct = "true" in "".join(output).lower()
        except Exception: is_correct = False

    if is_correct and request.student_id and str(request.student_id) != "guest":
        save_user_progress(request.student_id, request.task_id)

    with open("user_stats.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()},{request.student_id},{task.get('topic','unknown')},{is_correct}\n")

    return {"is_correct": is_correct, "topic": task.get("topic"), "correct_was": correct_answer if not is_correct else None}

@app.post("/review/")
async def explain_mistake(request: ReviewRequest):
    content = request.task_text if request.task_text else "Текст задачи не предоставлен"
    prompt = (f"Объясни задачу максимально просто и понятно, 'на пальцах'. Текст: {content}. Ответ ученика: {request.user_answer}. Объясни почему неверно." 
              if request.simplify else 
              f"Напиши подробное пошаговое объяснение. Текст: {content}. Ответ ученика: {request.user_answer}.")
    
    input_data = {"prompt": prompt}
    if request.image_url: input_data["image"] = request.image_url

    try:
        output = replicate.run("google/gemini-3-flash", input=input_data)
        return {"explanation": "".join(output).replace("\n", "<br>")}
    except Exception:
        return {"explanation": "Ошибка при генерации разбора."}

# --- АДМИНКА (НАЧИСЛЕНИЕ ВК КРЕДИТОВ И РАССЫЛКА ЧЕРЕЗ БРАУЗЕР) ---
@app.get("/admin/give")
async def admin_give_credits(target_id: str, amount: int, key: str = Query(None)):
    if key != "super-repetitor-2026":
        return {"error": "Доступ закрыт"}
    
    init_vk_user(target_id) # Убеждаемся, что юзер есть в базе
    new_balance = change_vk_credits(target_id, amount)
    
    # Отправляем уведомление в личку ВК
    await send_vk_message(target_id, f"🎁 Подарок от администратора!\nНа ваш баланс зачислено: {amount} кр.\nТекущий баланс: {new_balance} кр.")
    
    return {
        "success": True, 
        "message": f"Пользователю ВК ({target_id}) начислено {amount} кр.",
        "new_balance": new_balance
    }

@app.get("/admin/sendall_vk")
async def admin_sendall_vk(text: str, key: str = Query(None)):
    if key != "super-repetitor-2026":
        return {"error": "Доступ закрыт"}
        
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    for user in users:
        vk_id = user[0]
        # Рассылаем всем новость
        success = await send_vk_message(vk_id, f"📢 Новость Нейро-Репетитора:\n\n{text}")
        if success:
            count += 1
        
        await asyncio.sleep(0.1)  # <--- ВОТ ЭТА ПАУЗА (100 миллисекунд)
            
    return {"success": True, "message": f"Рассылка завершена. Доставлено: {count} пользователям."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
