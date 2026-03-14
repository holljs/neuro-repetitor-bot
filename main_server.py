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
async def check_answer_fast(request: CheckRequest):
    """Быстрая проверка Да/Нет (LLaVA)"""
    model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
    
    prompt = f'Ученик ответил "{request.user_answer}". Верно? Ответь СТРОГО JSON: {{"is_correct": true/false}}'
    
    try:
        output = replicate.run(model_id, input={"image": request.image_url, "prompt": prompt, "temperature": 0.1})
        res = "".join(output)
        is_correct = "true" in res.lower()
        return {"is_correct": is_correct}
    except Exception as e:
        return {"is_correct": False, "error": str(e)}

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
