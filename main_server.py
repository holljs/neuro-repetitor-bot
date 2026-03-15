import os
import logging
import base64
import random
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# !!! ВАЖНО: Импортируй свой модуль базы данных !!!
# Предполагаем, что файл называется database.py и в нем есть объект db
# from database import db 

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NeuroRepetitor")

load_dotenv()

# --- НАСТРОЙКИ ПУТЕЙ ---
QUESTIONS_DIR = Path("questions")
DB_FILE = QUESTIONS_DIR / "oge_math.json"

try:
    if DB_FILE.exists():
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            ALL_TASKS = json.load(f)
        logger.info(f"✅ База задач загружена: {len(ALL_TASKS)} шт.")
    else:
        ALL_TASKS = []
        logger.warning("⚠️ Файл базы задач не найден!")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки базы: {e}")
    ALL_TASKS = []

app = FastAPI(title="Neuro Repetitor API", version="1.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- МОДЕЛИ ДАННЫХ ---
class CheckRequest(BaseModel):
    user_answer: str
    image_url: str
    student_id: Optional[int] = None

class ReviewRequest(BaseModel):
    user_answer: str
    image_url: str
    student_id: Optional[int] = None
    simplify: bool = False

class ReportRequest(BaseModel):
    task_id: str

# --- МАРШРУТЫ ---

@app.get("/")
async def root():
    return {"status": "online", "server_time": datetime.utcnow().isoformat()}

@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge_math"):
    """Случайная задача с поддержкой тем и ответов"""
    tasks_pool = [t for t in ALL_TASKS if t.get("exam_type") == exam_type]
    if not tasks_pool: tasks_pool = ALL_TASKS
    if not tasks_pool: raise HTTPException(status_code=500, detail="База пуста")
    
    task = random.choice(tasks_pool)
    return {
        "id": task.get("id", "unknown"),
        "topic": task.get("topic", "Общая тема"),
        "text": task.get("text", ""),
        "image": task.get("image", ""),
        "answer": task.get("answer", "")
    }

@app.post("/start_test_payment/")
async def pay_for_test(request: ReportRequest):
    """Списание 3 кредитов за начало теста"""
    student_id = int(request.task_id) # В JS мы передаем USER_ID в поле task_id
    
    # balance = db.get_balance(student_id)
    # if balance is None or balance < 3:
    #     return {"success": False, "error": "Недостаточно кредитов (нужно 3)"}
    
    # db.update_balance(student_id, -3)
    logger.info(f"💰 Списано 3 кредита у {student_id}")
    return {"success": True, "new_balance": 97} # Заглушка баланса

@app.post("/check/")
async def check_answer_smart(request: CheckRequest):
    """Умная проверка: сравниваем ответ ученика с эталоном из базы через ИИ"""
    
    # 1. Ищем задачу в ALL_TASKS по ID (который пришел из фронтенда)
    # В CheckRequest должно быть поле task_id
    task_id = getattr(request, 'task_id', None)
    task_in_db = next((t for t in ALL_TASKS if t.get("id") == task_id), None)
    
    if not task_in_db or not task_in_db.get("answer"):
        logger.warning(f"⚠️ Ответ для задачи {task_id} не найден в базе")
        return {"is_correct": False, "error": "Ответ отсутствует в базе"}

    correct_answer = str(task_in_db["answer"])
    user_answer = request.user_answer.strip()

    # 2. Быстрая проверка на точное совпадение (чтобы не тратить токены)
    if user_answer.replace('.', ',') == correct_answer.replace('.', ','):
        return {"is_correct": True}

    # 3. Если не совпало "в лоб", вызываем Gemini как эксперта
    model_id = "google/gemini-3-flash" 
    
    prompt = f"""
    Ты — эксперт-математик. Проверь, совпадает ли ответ ученика с правильным ответом.
    Они могут быть записаны по-разному, но быть математически равны.
    
    ПРАВИЛЬНЫЙ ОТВЕТ: {correct_answer}
    ОТВЕТ УЧЕНИКА: {user_answer}
    
    Примеры эквивалентности:
    - "0,5" и "1/2" — ВЕРНО
    - "x=2" и "2" — ВЕРНО
    - "sqrt(12)" и "2*sqrt(3)" — ВЕРНО
    - "корень из 2" и "sqrt(2)" — ВЕРНО
    
    Если ответы равны, ответь 'true', если нет — 'false'.
    Верни строго JSON: {{"is_correct": true/false}}
    """

    try:
        # Важно: Gemini 3 Flash очень быстрая и дешевая
        output = replicate.run(model_id, input={"prompt": prompt})
        res = "".join(output).lower()
        is_correct = "true" in res
        return {"is_correct": is_correct}
    except Exception as e:
        logger.error(f"❌ Ошибка ИИ-проверки: {e}")
        # Запасной вариант: простое сравнение
        return {"is_correct": user_answer == correct_answer}

@app.post("/review/")
async def review_answer_detailed(request: ReviewRequest):
    """Подробный бесплатный разбор на Gemini 3 Flash"""
    # Самая дешевая модель из твоих документов 
    model_id = "google/gemini-3-flash" 

    if request.simplify:
        prompt = f"Объясни задачу 'на яблоках'. Ответ ученика: {request.user_answer}"
    else:
        prompt = f"Напиши пошаговое решение задачи. Ответ ученика был: {request.user_answer}"

    try:
        output = replicate.run(model_id, input={"images": [request.image_url], "prompt": prompt})
        return {"explanation": "".join(output).strip()}
    except Exception as e:
        logger.error(f"Review Error: {e}")
        return {"explanation": "Ошибка ИИ, попробуй позже."}

@app.post("/report_task/")
async def report_broken_task(request: ReportRequest):
    with open("reports.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()}: Жалоба на ID {request.task_id}\n")
    return {"success": True}

# --- АДМИНКА ---
@app.get("/admin/add_credits")
async def add_credits(user_id: int, amount: int, key: str):
    if key != "твой_секретный_ключ": return {"error": "No access"}
    # db.update_balance(user_id, amount)
    return {"success": True, "user": user_id, "added": amount}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
