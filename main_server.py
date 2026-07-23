import os
import time
import logging
import random
import json
import re
import sqlite3
import httpx  
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

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from yookassa import Configuration, Payment

load_dotenv()
app = FastAPI(title="Neuro Repetitor API", version="3.0.0")

# Настройка ЮKassa
Configuration.configure(
    os.getenv("YUKASSA_SHOP_ID", "TEST_ID"), 
    os.getenv("YUKASSA_SECRET_KEY", "TEST_KEY")
)

VK_APP_SECRET = os.getenv("VK_APP_SECRET", "ТВОЙ_СЕКРЕТНЫЙ_КЛЮЧ_ВК")
INTERNAL_BOT_TOKEN = os.getenv("INTERNAL_BOT_TOKEN", "tg-super-secret-password-2026-xyz")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

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
    "geography_part1": "🌍 География (Часть 1)", "biology_part1": "🧬 Биология",
    "informatics_part1": "💻 Информатика", "history_part1": "📜 История", "social_part1": "📊 Обществознание",
    "informatics_ege": "💻 Информатика ЕГЭ", "geography_ege": "🌍 География ЕГЭ", "physics_ege": "⚡ Физика ЕГЭ",
    "ege_english": "🇬🇧 Английский ЕГЭ", "ege_literature": "📚 Литература ЕГЭ",
    "olymp_math": "🏆 Олимпиада Математика", "olymp_russian": "🏆 Олимпиада Русский язык",
    "olymp_inf": "🏆 Олимпиада Информатика", "olymp_phys": "🏆 Олимпиада Физика", "olymp_chem": "🏆 Олимпиада Химия",
    "vpr_math": "📝 ВПР Математика", "vpr_russian": "📝 ВПР Русский язык", "vpr_history": "📝 ВПР История"
}

if Path("questions").exists():
    app.mount("/questions", StaticFiles(directory="questions"), name="questions")

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=False, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NeuroRepetitor")

# =========================================================================
# УНИВЕРСАЛЬНЫЙ ИИ-ДВИЖОК НА REPLICATE
# =========================================================================
async def ask_replicate(
    system_prompt: str, 
    user_prompt: str, 
    image_url: Optional[str] = None, 
    max_tokens: int = 1000, 
    response_json: bool = False
) -> str:
    """
    Автоматически переключается:
    - Есть картинка -> google/gemini-1.5-flash (Мультимодальная)
    - Только текст  -> openai/gpt-4.1-nano (Супербыстрая и дешевая)
    """
    if not REPLICATE_API_TOKEN:
        logger.error("❌ Ошибка: REPLICATE_API_TOKEN не найден в .env!")
        raise Exception("REPLICATE_API_TOKEN не настроен.")

    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    has_image = image_url and image_url.strip().lower() not in ["", "none", "null"]

    if has_image:
        model_name = "google/gemini-1.5-flash"
        payload = {
            "input": {
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "image": image_url,
                "max_tokens": max_tokens,
                "temperature": 0.2 if response_json else 0.4
            }
        }
    else:
        model_name = "openai/gpt-4.1-nano"
        prompt_text = f"{system_prompt}\n\n{user_prompt}"
        if response_json:
            prompt_text += "\nОтвечай СТРОГО в формате валидного JSON объекта без любого другого текста вокруг."

        payload = {
            "input": {
                "prompt": prompt_text,
                "max_tokens": max_tokens,
                "temperature": 0.1 if response_json else 0.4
            }
        }

    url = f"https://api.replicate.com/v1/models/{model_name}/predictions"

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)

            if response.status_code in [200, 201]:
                prediction = response.json()
                get_url = prediction.get("urls", {}).get("get")
                if not get_url:
                    break

                # Ожидание результата генерации (Polling)
                for _ in range(35):
                    await asyncio.sleep(0.8)
                    async with httpx.AsyncClient() as client:
                        poll_resp = await client.get(get_url, headers=headers, timeout=10.0)

                    if poll_resp.status_code == 200:
                        poll_data = poll_resp.json()
                        status = poll_data.get("status")

                        if status == "succeeded":
                            output = poll_data.get("output", "")
                            if isinstance(output, list):
                                return "".join(output).strip()
                            return str(output).strip()

                        elif status in ["failed", "canceled"]:
                            logger.error(f"❌ Replicate статус ошибки: {poll_data.get('error')}")
                            break

            else:
                logger.warning(f"⚠️ Ошибка от Replicate API ({response.status_code}): {response.text}")

        except Exception as exc:
            logger.warning(f"⚠️ Ошибка сети Replicate (попытка {attempt + 1}): {exc}")
            if attempt == max_attempts - 1:
                break
            await asyncio.sleep(1.0)

    return '{"is_correct": false}' if response_json else "Ошибка генерации ответа ИИ."

# =========================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И АВТОРИЗАЦИЯ
# =========================================================================
def verify_vk_auth(student_id: str, vk_params: str) -> bool:
    if vk_params == INTERNAL_BOT_TOKEN: 
        return True
    if not vk_params or "sign=" not in vk_params: 
        return False
        
    query_params = dict(parse_qsl(vk_params.lstrip('?'), keep_blank_values=True))
    vk_params_dict = {k: v for k, v in query_params.items() if k.startswith('vk_')}
    sorted_vk_params = dict(sorted(vk_params_dict.items()))
    encoded_params = urlencode(sorted_vk_params)

    hash_code = hmac.new(VK_APP_SECRET.encode('utf-8'), encoded_params.encode('utf-8'), hashlib.sha256).digest()
    expected_sign = base64.urlsafe_b64encode(hash_code).decode('utf-8').rstrip('=')
    
    return query_params.get('sign') == expected_sign

async def send_vk_message(user_id: str, message: str):
    vk_token = os.getenv("VK_REPETITOR_TOKEN")
    if not vk_token: 
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
                return "error" not in result
    except Exception: 
        return False

QUESTIONS_DIR = Path("questions")
PROGRESS_FILE = Path("user_progress.json")

# Динамическая автозагрузка баз заданий из папки /questions/
DATABASES = {}
if QUESTIONS_DIR.exists():
    for json_file in QUESTIONS_DIR.glob("*.json"):
        if json_file.name == "user_progress.json": 
            continue
        db_key = json_file.stem
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                DATABASES[db_key] = json.load(f)
            logger.info(f"📦 Успешно загружена база: {db_key} ({len(DATABASES[db_key])} задач)")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки {json_file.name}: {e}")

def init_vk_db():
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, credits INTEGER DEFAULT 0, last_activity TIMESTAMP)")
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN got_reward INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass 
    conn.commit()
    conn.close()

init_vk_db()

def init_vk_user(user_id: str) -> int:
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, credits, last_activity, got_reward) VALUES (?, ?, datetime('now'), 0)", (user_id, 6))
        conn.commit()
        balance = 6
        asyncio.create_task(send_vk_message(str(ADMIN_VK_IDS[0]), f"👤 Новый ученик в приложении!\nСсылка: vk.com/id{user_id}"))
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
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f: 
            return json.load(f).get(str(user_id), [])
    return []

def save_user_progress(user_id: str, task_id: str):
    data = {}
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f: 
            data = json.load(f)
    uid = str(user_id)
    if uid not in data: 
        data[uid] = []
    if task_id not in data[uid]:
        data[uid].append(task_id)
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f: 
            json.dump(data, f, ensure_ascii=False, indent=2)

def clean_and_normalize(text: str) -> str:
    if not text: 
        return ""
    cleaned = str(text)
    cleaned = re.sub(r'[\u2012\u2013\u2014\u2212]', '-', cleaned)  
    cleaned = cleaned.replace(',', '.')  
    cleaned = re.sub(r'[^\w\-.]', '', cleaned)  
    return cleaned.strip().lower()

def check_student_answer(student_ans, correct_ans) -> bool:
    if not student_ans or not correct_ans: 
        return False
    norm_student = clean_and_normalize(student_ans)
    norm_correct = clean_and_normalize(correct_ans)
    
    if not norm_student or not norm_correct: 
        return False
    if norm_student == norm_correct: 
        return True
    
    if norm_correct.isdigit() and norm_student.isdigit():
        if len(norm_student) == len(norm_correct) and sorted(norm_student) == sorted(norm_correct):
            return True
            
    return False

# =========================================================================
# MODELS & SCHEMAS
# =========================================================================
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

# =========================================================================
# ENDPOINTS
# =========================================================================
@app.post("/create_payment/")
async def create_payment(request: BuyRequest):
    if not verify_vk_auth(request.student_id, request.vk_params):
        return {"success": False, "error": "Ошибка безопасности ВК."}

    vk_app_id = "51800000"
    if request.vk_params:
        query_params = dict(parse_qsl(request.vk_params.lstrip('?'), keep_blank_values=True))
        if 'vk_app_id' in query_params:
            vk_app_id = query_params['vk_app_id']

    price_map = {15: 150.0, 100: 700.0}
    if request.amount not in price_map:
        return {"success": False, "error": "Неверный пакет кредитов."}
    
    actual_price = price_map[request.amount]

    try:
        idempotency_key = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {"value": f"{actual_price:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": f"https://vk.com/app{vk_app_id}"},
            "capture": True,
            "description": f"Пополнение баланса Нейро-Репетитор ({request.amount} кр.)",
            "metadata": {"student_id": request.student_id, "amount": request.amount}
        }, idempotency_key)
        return {"success": True, "confirmation_url": payment.confirmation.confirmation_url}
    except Exception:
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
                await send_vk_message(str(ADMIN_VK_IDS[0]), f"💰 ОПЛАТА!\nУченик vk.com/id{student_id} купил {amount} кр.")
        return {"status": "ok"}
    except Exception: 
        return {"status": "error"}

@app.post("/start_test_payment/")
async def pay_for_test(request: PaymentRequest):
    student_id = str(request.student_id)
    if not verify_vk_auth(student_id, request.vk_params):
        return {"success": False, "error": "Ошибка безопасности ВК."}
        
    cost = 3 if request.test_mode == "pro" else 2 
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
    if not db: 
        raise HTTPException(status_code=500, detail=f"База {exam_type} пуста или не загружена")
    
    solved_ids = get_user_progress(student_id)
    available_tasks = [t for t in db if str(t.get("id")) not in solved_ids and str(t.get("answer", "")).strip().lower() not in ["", "undefined", "none", "-", "--", "---", "null"]]
    
    if not available_tasks:
        return {"id": "done", "topic": "done", "text": "🎉 Все задачи решены!", "image": "", "done": True}
    
    task = random.choice(available_tasks)
    img_path = task.get("image", "")
    
    if img_path and not img_path.startswith("http") and not img_path.startswith("questions/"):
        clean_name = img_path.split('/')[-1]
        base_prefix = exam_type.split('_')[0]
        
        if base_prefix in ["olymp", "vpr"]:
            img_path = f"questions/images_{exam_type}/{clean_name}"
        else:
            if exam_type == "oge_physics": img_path = f"questions/images_oge_physics/{clean_name}"
            elif exam_type == "oge_chemistry": img_path = f"questions/images_oge_chemistry/{clean_name}"
            elif exam_type == "oge_geography": img_path = f"questions/images_oge_geography/{clean_name}"
            elif exam_type == "math_ege": img_path = f"questions/images_ege_math/{clean_name}"
            elif exam_type == "inf_ege": img_path = f"questions/images_ege_inf/{clean_name}"
            elif exam_type == "geo_ege": img_path = f"questions/images_ege_geo/{clean_name}"
            elif exam_type == "phys_ege": img_path = f"questions/images_ege_phys/{clean_name}"    
            else: img_path = f"questions/images_oge_math/{task.get('topic', 'topic_01')}/{clean_name}"

    return { 
        "id": task.get("id", "unknown"), 
        "topic": task.get("topic", "Общая тема"), 
        "text": task.get("task_text", task.get("text", "")), 
        "image": img_path 
    }

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
        if task: 
            break

    if not task: 
        return {"is_correct": False, "error": "Задача не найдена"}

    correct_answer = str(task.get("answer", ""))
    is_correct = check_student_answer(request.user_answer, correct_answer)

    solved_ids = get_user_progress(str(request.student_id))
    if str(request.task_id) in solved_ids:
        return {"is_correct": is_correct, "topic": task.get("topic"), "correct_was": correct_answer if not is_correct else None}
    
    # 🔥 ИИ-АРБИТР НА GPT-4.1-NANO
    if not is_correct and correct_answer != "---":
        try:
            sys_prompt = "Ты — беспристрастный арбитр школьных ответов. Определи, совпадает ли ответ ученика с эталоном по смыслу."
            user_prompt = f"Эталон: '{correct_answer}'. Ответ ученика: '{request.user_answer}'. Они эквивалентны? Напиши строго JSON: {{\"is_correct\": true}} или {{\"is_correct\": false}}"
            
            res_ai = await ask_replicate(
                system_prompt=sys_prompt, 
                user_prompt=user_prompt, 
                max_tokens=100, 
                response_json=True
            )
            
            match = re.search(r'\{.*\}', res_ai, re.DOTALL)
            if match:
                ai_data = json.loads(match.group(0))
                is_correct = ai_data.get("is_correct", False)
        except Exception as e: 
            logger.error(f"⚠️ Ошибка ИИ-Арбитра: {e}")
            is_correct = False

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
    base_prompt = "Отвечай ПРОСТЫМ понятным текстом для школьника. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать LaTeX (знаки $ или $$), формулы в косых чертах. Пиши разбор красиво, структурированно, с Markdown."
    
    user_prompt = (
        f"Объясни задачу 'на пальцах'. Текст задания: {content}. Неправильный ответ ученика: {request.user_answer}. Укажи на ошибку простым языком."  
        if request.simplify else  
        f"Напиши короткое пошаговое объяснение решения этой задачи. Текст задания: {content}. Неправильный ответ ученика: {request.user_answer}."
    )
    
    try:
        # Автоматически запустит Gemini Flash (если есть картинка) или GPT Nano (если только текст)
        explanation = await ask_replicate(
            system_prompt=base_prompt, 
            user_prompt=user_prompt, 
            image_url=request.image_url, 
            max_tokens=1000
        )
        return {"explanation": explanation.replace("\n", "<br>")}
    except Exception: 
        return {"explanation": "Ошибка при генерации разбора."}

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
    if not request.mistakes: 
        return {"analysis": "У тебя нет ошибок! Ты молодец! 🎉"}

    sys_prompt = "Ты эксперт-аналитик пробелов знаний. Отвечай кратко, понятным языком, БЕЗ LATEX И ЗНАКОВ ДОЛЛАРА. Выдели темы, которые нужно повторить."
    user_prompt = "Проанализируй ошибки ученика в тесте и выяви пробелы:\n\n"
    for i, m in enumerate(request.mistakes): 
        user_prompt += f"{i+1}. Задача: {m.task_text[:250]}\n"

    try:
        analysis = await ask_replicate(
            system_prompt=sys_prompt, 
            user_prompt=user_prompt, 
            max_tokens=800
        )
        return {"analysis": analysis.replace("\n", "<br>")}
    except Exception: 
        return {"analysis": "Не удалось сгенерировать анализ."}

@app.get("/profile_base/")
async def get_profile_base(student_id: str, vk_params: str = None):
    if not verify_vk_auth(student_id, vk_params): 
        raise HTTPException(status_code=403, detail="Signature invalid")
        
    current_balance = init_vk_user(student_id)
    
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT got_reward FROM users WHERE user_id=?", (student_id,))
    row = cursor.fetchone()
    got_reward = row[0] if row else 0
    conn.close()

    total_solved = 0
    active_subjects = set()
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
                        
    return {
        "balance": current_balance, 
        "total_solved": total_solved, 
        "active_subjects": list(active_subjects), 
        "subject_counts": subject_counts, 
        "got_reward": got_reward
    }
    
@app.get("/analyze_subject/")
async def analyze_subject(student_id: str, subject_key: str, vk_params: str = None):
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
                        
    if len(user_records) < 8: 
        return {"analysis": f"⏳ <b>Недостаточно данных.</b> Ты решил(а) всего {len(user_records)} задач из этого предмета. Пройди хотя бы один полный тест (10 вопросов), чтобы ИИ смог составить точный аналитический отчет!"}
        
    topic_history = {}
    for r in user_records:
        t = r["topic"]
        if t not in topic_history: 
            topic_history[t] = []
        topic_history[t].append("✅" if r["is_correct"] else "❌")

    sys_prompt = "Ты ИИ-куратор учебной платформы. Напиши короткий мотивирующий отчет (2-3 абзаца). ОТВЕЧАЙ СТРОГО БЕЗ LATEX И БЕЗ МАТЕМАТИЧЕСКИХ СПЕЦСИМВОЛОВ."
    user_prompt = "Вот история ответов ученика по предмету. Темы:\n\n"
    for t, history in topic_history.items(): 
        user_prompt += f"- {TOPIC_NAMES.get(t, t)}: {' '.join(history[-20:])}\n"
    user_prompt += "\nУкажи сильные и слабые темы, дай конкретные советы по подготовке."

    try:
        analysis = await ask_replicate(
            system_prompt=sys_prompt, 
            user_prompt=user_prompt, 
            max_tokens=800
        )
        return {"analysis": analysis.replace("\n", "<br>")}
    except Exception: 
        return {"analysis": "⚠️ Ошибка генерации."}

class RewardRequest(BaseModel):
    student_id: str
    vk_params: str

@app.post("/reward_subscription/")
async def reward_subscription(req: RewardRequest):
    if not verify_vk_auth(req.student_id, req.vk_params): 
        return {"success": False}
    conn = sqlite3.connect("vk_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT got_reward FROM users WHERE user_id=?", (req.student_id,))
    row = cursor.fetchone()
    
    if row and row[0] == 1:
        conn.close()
        return {"success": False, "message": "Bonus already received"}
    
    cursor.execute("UPDATE users SET credits = credits + 3, got_reward = 1 WHERE user_id=?", (req.student_id,))
    conn.commit()
    conn.close()
    
    asyncio.create_task(send_vk_message(str(ADMIN_VK_IDS[0]), f"🔔 Подписка на рассылку!\nУченик vk.com/id{req.student_id} получил бонус +3 кр."))
    return {"success": True}

class FinishTestRequest(BaseModel):
    student_id: str
    score: int
    total: int
    vk_params: str
    
@app.post("/notify_test_finish/")
async def notify_test_finish(req: FinishTestRequest):
    if not verify_vk_auth(req.student_id, req.vk_params): 
        return {"success": False}
    asyncio.create_task(send_vk_message(str(ADMIN_VK_IDS[0]), f"🎓 Тест завершен!\nУченик: vk.com/id{req.student_id}\nРезультат: {req.score} из {req.total}"))
    return {"success": True}

# =========================================================================
# АДМИНКА И ВК-ВЕБХУК
# =========================================================================
ADMIN_VK_IDS = [233876992] 

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

        if sender_id in ADMIN_VK_IDS:
            if text.lower().startswith("рассылка"):
                broadcast_text = text[8:].strip()
                if not broadcast_text:
                    await send_vk_message(str(sender_id), "⚠️ Ошибка. Напиши: Рассылка [твой текст]")
                    return HTMLResponse(content="ok", status_code=200)
                
                await send_vk_message(str(sender_id), "⏳ Начинаю массовую рассылку...")
                conn = sqlite3.connect("vk_users.db")
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users")
                users = cursor.fetchall()
                conn.close()
                
                success = 0
                for u in users:
                    res = await send_vk_message(u[0], broadcast_text)
                    if res: 
                        success += 1
                    await asyncio.sleep(0.05) 
                
                await send_vk_message(str(sender_id), f"✅ Рассылка завершена!\nДоставлено: {success} из {len(users)}")
                return HTMLResponse(content="ok", status_code=200)

            parts = text.split()
            is_admin_command = (len(parts) == 2 and parts[0].isdigit() and (parts[1].isdigit() or (parts[1].startswith('-') and parts[1][1:].isdigit())))

            if is_admin_command:
                target_id = parts[0]
                amount = int(parts[1])
                init_vk_user(target_id)
                new_bal = change_vk_credits(target_id, amount)
                await send_vk_message(str(sender_id), f"✅ Успешно!\nПользователь: {target_id}\nНачислено: {amount}\nНовый баланс: {new_bal} кр.")

    return HTMLResponse(content="ok", status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
