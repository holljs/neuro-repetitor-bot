import os
import logging
import random
import json
import re
import sqlite3
import aiohttp  
import asyncio
import hmac
import hashlib
import base64
import uuid
from urllib.parse import urlencode, parse_qsl
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

# --- ИМПОРТ И ИНИЦИАЛИЗАЦИЯ ЮKASSA ---
from yookassa import Configuration, Payment

# --- ИНИЦИАЛИЗАЦИЯ ---
load_dotenv()
app = FastAPI(title="Neuro Repetitor API", version="2.4.0")

# Настраиваем ключи ЮКассы из .env (через U)
Configuration.configure(os.getenv("YUKASSA_SHOP_ID", "TEST_ID"), os.getenv("YUKASSA_SECRET_KEY", "TEST_KEY"))

# --- СЕКРЕТНЫЕ КЛЮЧИ ДЛЯ БЕЗОПАСНОСТИ ---
VK_APP_SECRET = os.getenv("VK_APP_SECRET", "ТВОЙ_СЕКРЕТНЫЙ_КЛЮЧ_ВК")
INTERNAL_BOT_TOKEN = os.getenv("INTERNAL_BOT_TOKEN", "tg-super-secret-password-2026-xyz")

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
    "geography_ege": "🌍 География ЕГЭ",
    "physics_ege": "⚡ Физика ЕГЭ",
    "ege_english": "🇬🇧 Английский ЕГЭ",
    "ege_literature": "📚 Литература ЕГЭ" # <--- ДОБАВИТЬ ЭТУ СТРОКУ
}

if Path("questions").exists():
    app.mount("/questions", StaticFiles(directory="questions"), name="questions")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NeuroRepetitor")

def verify_vk_auth(student_id: str, vk_params: str) -> bool:
    if student_id in ["54451631", "12345678", "guest", "None", None]:
        return True
    if vk_params == INTERNAL_BOT_TOKEN:
        return True
    if not vk_params or "sign=" not in vk_params:
        logger.warning(f"⚠️ Попытка взлома (нет подписи ВК)! ID: {student_id}")
        return False
        
    query_params = dict(parse_qsl(vk_params.lstrip('?'), keep_blank_values=True))
    if 'vk_user_id' not in query_params or str(query_params['vk_user_id']) != str(student_id):
        return False

    vk_params_dict = {k: v for k, v in query_params.items() if k.startswith('vk_')}
    sorted_vk_params = dict(sorted(vk_params_dict.items()))
    encoded_params = urlencode(sorted_vk_params)

    hash_code = hmac.new(VK_APP_SECRET.encode('utf-8'), encoded_params.encode('utf-8'), hashlib.sha256).digest()
    expected_sign = base64.urlsafe_b64encode(hash_code).decode('utf-8').rstrip('=')
    
    if query_params.get('sign') != expected_sign:
        return False
    return True

async def send_vk_message(user_id: str, message: str):
    vk_token = os.getenv("VK_TOKEN")
    if not vk_token: return False
    url = "https://api.vk.com/method/messages.send"
    params = {"user_id": user_id, "message": message, "random_id": random.randint(1, 2147483647), "v": "5.131", "access_token": vk_token}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=params) as resp:
                result = await resp.json()
                if "error" in result: return False
                return True
    except Exception: return False

QUESTIONS_DIR = Path("questions")
PROGRESS_FILE = Path("user_progress.json")
DATABASES = {
    "oge_math": [], "oge_english": [], "oge_russian": [], 
    "oge_chemistry": [], "oge_physics": [], "oge_geography": [],
    "oge_biology": [], "oge_informatics": [], "oge_history": [], "oge_social": [],
    "math_ege": [], "russian_ege": [],
    "inf_ege": [], "geo_ege": [], "phys_ege": [], "ege_english": [], "chem_ege": [],
    "ege_literature": [] # <--- ДОБАВИТЬ ЭТУ СТРОКУ
}

def load_database(filename, db_key):
    filepath = QUESTIONS_DIR / filename
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f: DATABASES[db_key] = json.load(f)
            logger.info(f"✅ База {db_key} загружена: {len(DATABASES[db_key])} шт.")
        except Exception as e: logger.error(f"❌ Ошибка: {e}")

# Загружаем все базы
for db_key in DATABASES.keys():
    load_database(f"{db_key}.json", db_key)

def init_vk_db():
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, credits INTEGER DEFAULT 0, last_activity TIMESTAMP)")
    conn.commit()
    conn.close()

init_vk_db()

def init_vk_user(user_id: str) -> int:
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, credits, last_activity) VALUES (?, ?, datetime('now'))", (user_id, 16))
        conn.commit()
        balance = 16
    else:
        cursor.execute("UPDATE users SET last_activity=datetime('now') WHERE user_id=?", (user_id,))
        conn.commit()
        balance = user[0]
    conn.close()
    return balance

def change_vk_credits(user_id: str, amount: int) -> int:
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    new_balance = cursor.fetchone()[0]
    conn.close()
    return new_balance

def get_user_progress(user_id: str):
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f: return json.load(f).get(str(user_id), [])
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
    if not student_ans or not correct_ans: return False
    student_ans = str(student_ans).upper()
    correct_ans = str(correct_ans).upper()
    if correct_ans.isdigit():
        return re.sub(r'\D', '', student_ans) == correct_ans
    elif correct_ans.replace('.', '').replace(',', '').replace('-', '').isdigit():
        return student_ans.replace(" ", "").replace(",", ".") == correct_ans.replace(" ", "").replace(",", ".")
    else:
        return re.sub(r'[\s\-\.,;:]', '', student_ans) == re.sub(r'[\s\-\.,;:]', '', correct_ans)

class CheckRequest(BaseModel):
    user_answer: str
    task_id: str  
    student_id: Optional[str] = None
    vk_params: Optional[str] = None

class ReviewRequest(BaseModel):
    user_answer: str
    image_url: Optional[str] = None
    task_text: Optional[str] = None
    student_id: Optional[str] = None
    simplify: bool = False
    vk_params: Optional[str] = None

class PaymentRequest(BaseModel):
    student_id: Optional[str] = None
    task_id: Optional[str] = None
    test_mode: str = "standard"
    vk_params: Optional[str] = None

class BuyRequest(BaseModel):
    student_id: str
    amount: int
    price: float
    vk_params: str

# --- НОВЫЙ ЭНДПОИНТ: СОЗДАНИЕ ПЛАТЕЖА ЮKASSA ---
@app.post("/create_payment/")
async def create_payment(request: BuyRequest):
    if not verify_vk_auth(request.student_id, request.vk_params):
        return {"success": False, "error": "Ошибка безопасности ВК."}

    try:
        idempotency_key = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {
                "value": f"{request.price:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://vk.com/app51800000" # Замени на реальную ссылку твоего аппа ВК, если нужно
            },
            "capture": True,
            "description": f"Пополнение баланса Нейро-Репетитор ({request.amount} кр.)",
            "metadata": {
                "student_id": request.student_id,
                "amount": request.amount
            }
        }, idempotency_key)

        return {"success": True, "confirmation_url": payment.confirmation.confirmation_url}
    except Exception as e:
        logger.error(f"Ошибка создания платежа ЮКасса: {e}")
        return {"success": False, "error": "Не удалось создать платеж."}

# --- НОВЫЙ ЭНДПОИНТ: ВЕБХУК ОТ ЮKASSA ---
@app.post("/yookassa_webhook/")
async def yookassa_webhook(request: dict):
    try:
        if request.get('event') == 'payment.succeeded':
            obj = request['object']
            student_id = obj['metadata'].get('student_id')
            amount = int(obj['metadata'].get('amount'))
            
            if student_id and amount:
                new_balance = change_vk_credits(student_id, amount)
                logger.info(f"💰 ОПЛАТА: Юзер {student_id} купил {amount} кр. Баланс: {new_balance}")
                await send_vk_message(student_id, f"✅ Оплата прошла успешно!\nНа ваш баланс зачислено: {amount} кр.\nПриятного обучения!")
                
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Ошибка вебхука ЮКассы: {e}")
        return {"status": "error"}

@app.post("/start_test_payment/")
async def pay_for_test(request: PaymentRequest):
    student_id = str(request.student_id)
    if not verify_vk_auth(student_id, request.vk_params):
        return {"success": False, "error": "Ошибка безопасности ВК. Перезапустите приложение."}
        
    cost = 4 if request.test_mode == "pro" else 3
    if student_id in ["54451631", "12345678"]:
        return {"success": True, "new_balance": "unlimited", "cost": 0}
    
    current_balance = init_vk_user(student_id)
    if current_balance < cost:
        return {"success": False, "new_balance": current_balance, "cost": cost, "error": "Недостаточно кредитов"}
        
    new_balance = change_vk_credits(student_id, -cost)
    return {"success": True, "new_balance": new_balance, "cost": cost}

@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge_math", student_id: str = "guest", vk_params: str = None):
    if not verify_vk_auth(student_id, vk_params):
        raise HTTPException(status_code=403, detail="Ошибка авторизации")
        
    db = DATABASES.get(exam_type, [])
    if not db: raise HTTPException(status_code=500, detail="База пуста")
    solved_ids = get_user_progress(student_id)
    available_tasks = [t for t in db if str(t.get("id")) not in solved_ids]
    if not available_tasks:
        return {"id": "done", "topic": "done", "text": "🎉 Все задачи решены!", "image": "", "answer": "---", "done": True}
    
    task = random.choice(available_tasks)
    img_path = task.get("image", "")
    if img_path and not img_path.startswith("http") and not img_path.startswith("questions/"):
        clean_name = img_path.split('/')[-1]
        if exam_type == "oge_physics": img_path = f"questions/images_oge_physics/{clean_name}"
        elif exam_type == "oge_chemistry": img_path = f"questions/images_oge_chemistry/{clean_name}"
        elif exam_type == "oge_geography": img_path = f"questions/images_oge_geography/{clean_name}"
        elif exam_type == "math_ege": img_path = f"questions/images_ege_math/{clean_name}"
        elif exam_type == "inf_ege": img_path = f"questions/images_ege_inf/{clean_name}"
        elif exam_type == "geo_ege": img_path = f"questions/images_ege_geo/{clean_name}"
        elif exam_type == "phys_ege": img_path = f"questions/images_ege_phys/{clean_name}"    
        else: 
            topic = task.get("topic", "topic_01")
            img_path = f"questions/images_oge_math/{topic}/{clean_name}"

    return {"id": task.get("id", "unknown"), "topic": task.get("topic", "Общая тема"), "text": task.get("task_text", task.get("text", "")), "image": img_path, "answer": task.get("answer", "")}

@app.post("/check/")
async def check_answer_smart(request: CheckRequest):
    if not verify_vk_auth(str(request.student_id), request.vk_params):
        return {"is_correct": False, "error": "Ошибка безопасности"}
        
    db_name = "unknown"
    task = None
    for key, db in DATABASES.items():
        for t in db:
            if str(t.get("id")) == str(request.task_id):
                task = t
                db_name = key
                break
        if task: break

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
        f.write(f"{datetime.utcnow().isoformat()},{request.student_id},{task.get('topic','unknown')},{is_correct},{db_name}\n")

    return {"is_correct": is_correct, "topic": task.get("topic"), "correct_was": correct_answer if not is_correct else None}

@app.post("/review/")
async def explain_mistake(request: ReviewRequest):
    if not verify_vk_auth(str(request.student_id), request.vk_params):
        return {"explanation": "⚠️ Действие заблокировано системой безопасности."}
        
    content = request.task_text if request.task_text else "Текст задачи не предоставлен"
    prompt = (f"Объясни задачу максимально просто и понятно, 'на пальцах'. Текст: {content}. Ответ ученика: {request.user_answer}. Объясни почему неверно." 
              if request.simplify else 
              f"Напиши подробное пошаговое объяснение. Текст: {content}. Ответ ученика: {request.user_answer}.")
    
    input_data = {"prompt": prompt}
    if request.image_url: input_data["image"] = request.image_url

    try:
        output = replicate.run("google/gemini-3-flash", input=input_data)
        return {"explanation": "".join(output).replace("\n", "<br>")}
    except Exception: return {"explanation": "Ошибка при генерации разбора."}

class MistakeItem(BaseModel):
    task_text: str
    user_answer: str
    correct_answer: str

class AnalyzeGapsRequest(BaseModel):
    mistakes: list[MistakeItem]
    student_id: Optional[str] = None
    vk_params: Optional[str] = None

@app.post("/analyze_gaps/")
async def analyze_gaps(request: AnalyzeGapsRequest):
    if request.student_id and not verify_vk_auth(request.student_id, request.vk_params):
        return {"analysis": "Ошибка безопасности"}
    if not request.mistakes: return {"analysis": "У тебя нет ошибок! Ты молодец! 🎉"}

    prompt = "Ты опытный репетитор. Проанализируй ошибки ученика в тесте и выяви его пробелы в знаниях.\nВот задачи:\n\n"
    for i, m in enumerate(request.mistakes):
        short_text = m.task_text[:300] + "..." if len(m.task_text) > 300 else m.task_text
        prompt += f"{i+1}. Задача: {short_text}\n"

    prompt += "\nНа основе этих задач напиши краткий, дружелюбный анализ. Не решай эти задачи, просто дай диагноз по темам. Используй эмодзи."
    try:
        output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
        return {"analysis": "".join(output).replace("\n", "<br>")}
    except Exception: return {"analysis": "Не удалось сгенерировать анализ пробелов."}

@app.get("/profile_base/")
async def get_profile_base(student_id: str, vk_params: str = None):
    if not verify_vk_auth(student_id, vk_params):
        return {"balance": 0, "total_solved": 0, "active_subjects": []}
        
    current_balance = init_vk_user(student_id)
    total_solved = 0
    active_subjects = set()
    
    if Path("user_stats.log").exists():
        with open("user_stats.log", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4 and parts[1] == student_id:
                    total_solved += 1
                    if len(parts) >= 5 and parts[4] != "unknown":
                        active_subjects.add(parts[4])
                        
    return {
        "balance": current_balance,
        "total_solved": total_solved,
        "active_subjects": list(active_subjects)
    }

@app.get("/analyze_subject/")
async def analyze_subject(student_id: str, subject_key: str, vk_params: str = None):
    if not verify_vk_auth(student_id, vk_params):
        return {"analysis": "⚠️ Ошибка авторизации"}
        
    user_records = []
    if Path("user_stats.log").exists():
        with open("user_stats.log", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 5 and parts[1] == student_id and parts[4] == subject_key:
                    user_records.append({"topic": parts[2], "is_correct": parts[3].lower() == "true"})
                        
    if not user_records:
        return {"analysis": "У тебя пока нет истории по этому предмету. Реши пару задач!"}
        
    topic_history = {}
    for r in user_records:
        t = r["topic"]
        if t not in topic_history: topic_history[t] = []
        topic_history[t].append("✅" if r["is_correct"] else "❌")

    prompt = f"Ты умный ИИ-наставник. Вот история ответов ученика по предмету. Темы:\n\n"
    for t, history in topic_history.items():
        recent_history = history[-20:]
        prompt += f"- {TOPIC_NAMES.get(t, t)}: {' '.join(recent_history)}\n"
    prompt += "\nНапиши короткий мотивирующий отчет (2-3 абзаца). Укажи сильные и слабые темы. Обращайся на 'ты'."

    try:
        output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
        return {"analysis": "".join(output).replace("\n", "<br>")}
    except Exception:
        return {"analysis": "⚠️ Ошибка генерации отчета."}

@app.get("/admin/give")
async def admin_give_credits(target_id: str, amount: int, key: str = Query(None)):
    if key != "super-repetitor-2026": return {"error": "Доступ закрыт"}
    init_vk_user(target_id)
    new_balance = change_vk_credits(target_id, amount)
    await send_vk_message(target_id, f"🎁 Подарок от администратора!\nНа ваш баланс зачислено: {amount} кр.\nТекущий баланс: {new_balance} кр.")
    return {"success": True, "message": f"Начислено {amount} кр.", "new_balance": new_balance}

@app.get("/admin/sendall_vk")
async def admin_sendall_vk(text: str, key: str = Query(None)):
    if key != "super-repetitor-2026": return {"error": "Доступ закрыт"}
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    count = 0
    for user in users:
        vk_id = user[0]
        if await send_vk_message(vk_id, f"📢 Новость Нейро-Репетитора:\n\n{text}"): count += 1
        await asyncio.sleep(0.1)
    return {"success": True, "message": f"Доставлено: {count} пользователям."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
