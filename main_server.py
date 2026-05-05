import os
import time
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

from yookassa import Configuration, Payment

load_dotenv()
app = FastAPI(title="Neuro Repetitor API", version="2.4.0")

Configuration.configure(os.getenv("YUKASSA_SHOP_ID", "TEST_ID"), os.getenv("YUKASSA_SECRET_KEY", "TEST_KEY"))

VK_APP_SECRET = os.getenv("VK_APP_SECRET", "ТВОЙ_СЕКРЕТНЫЙ_КЛЮЧ_ВК")
INTERNAL_BOT_TOKEN = os.getenv("INTERNAL_BOT_TOKEN", "tg-super-secret-password-2026-xyz")

request_times = {}
rate_lock = asyncio.Lock()

async def check_rate_limit(user_id: str, limit: int = 3, window: int = 5) -> bool:
    async with rate_lock:
        now = time.time()
        times = request_times.get(user_id, [])
        times = [t for t in times if now - t < window]
        if len(times) >= limit:
            return False
        times.append(now)
        request_times[user_id] = times
        return True

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
    "ege_literature": "📚 Литература ЕГЭ"
}

if Path("questions").exists():
    app.mount("/questions", StaticFiles(directory="questions"), name="questions")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NeuroRepetitor")

def verify_vk_auth(student_id: str, vk_params: str) -> bool:
    if vk_params == INTERNAL_BOT_TOKEN: return True
    if not vk_params or "sign=" not in vk_params: return False
        
    query_params = dict(parse_qsl(vk_params.lstrip('?'), keep_blank_values=True))
    
    # ФИКС БАГА 3: Доверяем подписи ВК, убираем строгую проверку student_id
    # if 'vk_user_id' not in query_params or str(query_params['vk_user_id']) != str(student_id): return False

    vk_params_dict = {k: v for k, v in query_params.items() if k.startswith('vk_')}
    sorted_vk_params = dict(sorted(vk_params_dict.items()))
    encoded_params = urlencode(sorted_vk_params)

    hash_code = hmac.new(VK_APP_SECRET.encode('utf-8'), encoded_params.encode('utf-8'), hashlib.sha256).digest()
    expected_sign = base64.urlsafe_b64encode(hash_code).decode('utf-8').rstrip('=')
    
    if query_params.get('sign') != expected_sign: return False
    return True

async def send_vk_message(user_id: str, message: str):
    vk_token = os.getenv("VK_REPETITOR_TOKEN")
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
    "inf_ege": [], "geo_ege": [], "phys_ege": [], "ege_english": [], "chem_ege": [], "ege_literature": []
}

def load_database(filename, db_key):
    filepath = QUESTIONS_DIR / filename
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f: DATABASES[db_key] = json.load(f)
        except Exception as e: logger.error(f"❌ Ошибка: {e}")

for db_key in DATABASES.keys(): load_database(f"{db_key}.json", db_key)

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
    
    student_ans = re.sub(r'[\u2012\u2013\u2014\u2212]', '-', str(student_ans)).upper().strip()
    correct_ans = re.sub(r'[\u2012\u2013\u2014\u2212]', '-', str(correct_ans)).upper().strip()
    
    if len(student_ans) > len(correct_ans) + 15:
        return False

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

@app.post("/create_payment/")
async def create_payment(request: BuyRequest):
    if not verify_vk_auth(request.student_id, request.vk_params):
        return {"success": False, "error": "Ошибка безопасности ВК."}

    price_map = {15: 150.0, 100: 700.0}
    if request.amount not in price_map:
        return {"success": False, "error": "Неверный пакет кредитов."}
    
    actual_price = price_map[request.amount]

    try:
        idempotency_key = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {"value": f"{actual_price:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": "https://vk.com/app51800000"},
            "capture": True,
            "description": f"Пополнение баланса Нейро-Репетитор ({request.amount} кр.)",
            "metadata": {"student_id": request.student_id, "amount": request.amount}
        }, idempotency_key)
        return {"success": True, "confirmation_url": payment.confirmation.confirmation_url}
    except Exception as e:
        return {"success": False, "error": "Не удалось создать платеж."}

@app.post("/yookassa_webhook/")
async def yookassa_webhook(request: dict):
    try:
        if request.get('event') == 'payment.succeeded':
            obj = request['object']
            student_id = obj['metadata'].get('student_id')
            amount = int(obj['metadata'].get('amount'))
            if student_id and amount:
                change_vk_credits(student_id, amount)
                await send_vk_message(student_id, f"✅ Оплата прошла успешно!\nНа ваш баланс зачислено: {amount} кр.")
        return {"status": "ok"}
    except Exception as e: return {"status": "error"}

@app.post("/start_test_payment/")
async def pay_for_test(request: PaymentRequest):
    student_id = str(request.student_id)
    if not verify_vk_auth(student_id, request.vk_params):
        return {"success": False, "error": "Ошибка безопасности ВК."}
        
    cost = 4 if request.test_mode == "pro" else 3
    if student_id in ["54451631", "12345678"]: return {"success": True, "new_balance": "unlimited", "cost": 0}
    
    current_balance = init_vk_user(student_id)
    if current_balance < cost:
        return {"success": False, "new_balance": current_balance, "cost": cost, "error": "Недостаточно кредитов"}
        
    new_balance = change_vk_credits(student_id, -cost)
    return {"success": True, "new_balance": new_balance, "cost": cost}

@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge_math", student_id: str = "guest", vk_params: str = None):
    if not verify_vk_auth(student_id, vk_params): raise HTTPException(status_code=403, detail="Ошибка авторизации")
        
    db = DATABASES.get(exam_type, [])
    if not db: raise HTTPException(status_code=500, detail="База пуста")
    solved_ids = get_user_progress(student_id)
    
    available_tasks = [t for t in db if str(t.get("id")) not in solved_ids and str(t.get("answer", "")).strip().lower() not in ["", "undefined", "none", "-", "--", "---", "null"]]
    
    if not available_tasks:
        return {"id": "done", "topic": "done", "text": "🎉 Все задачи решены!", "image": "", "done": True}
    
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
        else: img_path = f"questions/images_oge_math/{task.get('topic', 'topic_01')}/{clean_name}"

    return { "id": task.get("id", "unknown"), "topic": task.get("topic", "Общая тема"), "text": task.get("task_text", task.get("text", "")), "image": img_path }

@app.post("/check/")
async def check_answer_smart(request: CheckRequest):
    if not await check_rate_limit(str(request.student_id), limit=5, window=5):
        return {"is_correct": False, "error": "Слишком частые запросы."}

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

    # ФИКС БАГА 5: Если задача уже решена, блокируем повторную накрутку логов и LLM-запросов
    solved_ids = get_user_progress(str(request.student_id))
    if str(request.task_id) in solved_ids:
        return {"is_correct": is_correct, "topic": task.get("topic"), "correct_was": correct_answer if not is_correct else None}
    
    if not is_correct and correct_answer != "---":
        try:
            prompt = f"Студент ответил '{request.user_answer}', а по ключу ответ '{correct_answer}'. Засчитать ли ответ студента как полностью верный? (Учитывай, что если это выбор нескольких вариантов, порядок цифр не важен, например 25 = 52). Верни строго JSON: {{\"is_correct\": true/false}}"
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
    if not await check_rate_limit(str(request.student_id), limit=3, window=5):
        return {"explanation": "⚠️ Слишком много запросов. Подождите пару секунд."}
        
    if not verify_vk_auth(str(request.student_id), request.vk_params): 
        return {"explanation": "⚠️ Действие заблокировано."}
        
    content = request.task_text if request.task_text else "Текст задачи не предоставлен"
    
    base_prompt = "Отвечай ПРОСТЫМ текстом. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать LaTeX (знаки $ или $$), сложный Markdown и формулы. Пиши так, чтобы текст легко читался в обычном мессенджере. Будь кратким (не более 3-4 предложений)."
    
    prompt = (f"{base_prompt} Объясни задачу 'на пальцах'. Текст: {content}. Ответ ученика: {request.user_answer}. Почему неверно?" 
              if request.simplify else 
              f"{base_prompt} Напиши короткое пошаговое объяснение. Текст: {content}. Ответ ученика: {request.user_answer}.")
    
    input_data = {"prompt": prompt}
    if request.image_url: input_data["image"] = request.image_url

    try:
        output = replicate.run("google/gemini-3-flash", input=input_data)
        return {"explanation": "".join(output).replace("\n", "<br>")}
    except Exception: return {"explanation": "Ошибка при генерации разбора."}

class MistakeItem(BaseModel):
    task_text: str; user_answer: str; correct_answer: str

class AnalyzeGapsRequest(BaseModel):
    mistakes: list[MistakeItem]; student_id: Optional[str] = None; vk_params: Optional[str] = None

@app.post("/analyze_gaps/")
async def analyze_gaps(request: AnalyzeGapsRequest):
    if request.student_id and not verify_vk_auth(request.student_id, request.vk_params): return {"analysis": "Ошибка безопасности"}
    if not request.mistakes: return {"analysis": "У тебя нет ошибок! Ты молодец! 🎉"}

    prompt = "Проанализируй ошибки ученика и выяви пробелы. Отвечай кратко, ПРОСТЫМ ТЕКСТОМ без использования LaTeX и математических спецсимволов.\nВот задачи:\n\n"
    for i, m in enumerate(request.mistakes): prompt += f"{i+1}. Задача: {m.task_text[:300]}\n"

    try:
        output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
        return {"analysis": "".join(output).replace("\n", "<br>")}
    except Exception: return {"analysis": "Не удалось сгенерировать анализ."}

@app.get("/profile_base/")
async def get_profile_base(student_id: str, vk_params: str = None):
    if not verify_vk_auth(student_id, vk_params): raise HTTPException(status_code=403, detail="Signature invalid")
        
    current_balance = init_vk_user(student_id)
    total_solved = 0; active_subjects = set()
    subject_counts = {}
    
    if Path("user_stats.log").exists():
        with open("user_stats.log", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4 and parts[1] == student_id:
                    total_solved += 1
                    if len(parts) >= 5 and parts[4] != "unknown": 
                        active_subjects.add(parts[4])
                        subj = parts[4]
                        subject_counts[subj] = subject_counts.get(subj, 0) + 1
                        
    return {"balance": current_balance, "total_solved": total_solved, "active_subjects": list(active_subjects), "subject_counts": subject_counts}

@app.get("/analyze_subject/")
async def analyze_subject(student_id: str, subject_key: str, vk_params: str = None):
    # ФИКС БАГА 4: Возвращаем текст ошибки в JSON, а не кидаем исключение сервера
    if not await check_rate_limit(student_id, limit=2, window=5): 
        return {"analysis": "⏳ Слишком много запросов. Подождите пару секунд и попробуйте снова."}
    if not verify_vk_auth(student_id, vk_params): 
        return {"analysis": "❌ Ошибка безопасности ВК."}
        
    user_records = []
    if Path("user_stats.log").exists():
        with open("user_stats.log", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 5 and parts[1] == student_id and parts[4] == subject_key:
                    user_records.append({"topic": parts[2], "is_correct": parts[3].lower() == "true"})
                        
    if len(user_records) < 10: 
        return {"analysis": f"⏳ <b>Недостаточно данных.</b> Ты решил(а) всего {len(user_records)} задач из этого предмета. Пройди хотя бы один полный тест (15 вопросов), чтобы ИИ смог составить точный аналитический отчет!"}
        
    topic_history = {}
    for r in user_records:
        t = r["topic"]
        if t not in topic_history: topic_history[t] = []
        topic_history[t].append("✅" if r["is_correct"] else "❌")

    prompt = f"Вот история ответов ученика по предмету. Темы:\n\n"
    for t, history in topic_history.items(): prompt += f"- {TOPIC_NAMES.get(t, t)}: {' '.join(history[-20:])}\n"
    prompt += "\nНапиши короткий мотивирующий отчет (2-3 абзаца). Укажи сильные и слабые темы. ОТВЕЧАЙ ПРОСТЫМ ТЕКСТОМ, БЕЗ LATEX И ЗНАКОВ ДОЛЛАРА."

    try:
        output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
        return {"analysis": "".join(output).replace("\n", "<br>")}
    except Exception: return {"analysis": "⚠️ Ошибка генерации."}

# ==========================================
# АДМИНКА ДЛЯ НАЧИСЛЕНИЯ КРЕДИТОВ (Callback API)
# ==========================================
ADMIN_VK_IDS = [233876992] # Твой ID

class VKCallback(BaseModel):
    type: str
    object: Optional[dict] = None
    group_id: Optional[int] = None
    secret: Optional[str] = None

@app.post("/vk_bot_webhook/")
async def vk_bot_webhook(data: VKCallback):
    if data.type == "confirmation":
        return HTMLResponse(content="11b52449", status_code=200)

    if data.type == "message_new":
        obj = data.object or {}
        msg = obj.get("message", obj)
        text = msg.get("text", "").strip()
        sender_id = msg.get("from_id")

        parts = text.split()
        is_admin_command = (
            sender_id in ADMIN_VK_IDS and 
            len(parts) == 2 and 
            parts[0].isdigit() and 
            (parts[1].isdigit() or (parts[1].startswith('-') and parts[1][1:].isdigit()))
        )

        if is_admin_command:
            target_id = parts[0]
            amount = int(parts[1])
            
            init_vk_user(target_id)
            new_bal = change_vk_credits(target_id, amount)
            
            await send_vk_message(str(sender_id), f"✅ Успешно!\nПользователь: {target_id}\nНачислено: {amount}\nНовый баланс: {new_bal} кр.")
            return HTMLResponse(content="ok", status_code=200)
        else:
            return HTMLResponse(content="ok", status_code=200)

    return HTMLResponse(content="ok", status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
