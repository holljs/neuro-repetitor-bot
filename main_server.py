import os
import logging
import random
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# --- ИНИЦИАЛИЗАЦИЯ ---
load_dotenv()
app = FastAPI(title="Neuro Repetitor API", version="1.3.0")

# --- НАСТРОЙКА CORS (Разрешаем GitHub и локалку) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://holljs.github.io", "http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NeuroRepetitor")

# --- ЗАГРУЗКА БАЗЫ ---
QUESTIONS_DIR = Path("questions")
DB_FILE = QUESTIONS_DIR / "oge_math.json"
ALL_TASKS = []

if DB_FILE.exists():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            ALL_TASKS = json.load(f)
        logger.info(f"✅ База задач загружена: {len(ALL_TASKS)} шт.")
    except Exception as e:
        logger.error(f"❌ Ошибка чтения JSON: {e}")

def normalize_math_text(text: str):
    if not text: return ""
    text = text.lower().replace(" ", "").replace(",", ".")
    text = re.sub(r'[\u2012\u2013\u2014\u2212]', '-', text)
    return text.strip()

# --- МОДЕЛИ ДАННЫХ ---
class CheckRequest(BaseModel):
    user_answer: str
    task_id: str  
    student_id: Optional[int] = None

class ReviewRequest(BaseModel):
    user_answer: str
    image_url: str
    student_id: Optional[int] = None
    simplify: bool = False

class ReportRequest(BaseModel):
    task_id: str
    student_id: Optional[int] = None

# --- ГЛАВНЫЙ МАРШРУТ ПРОВЕРКИ (С АНАЛИТИКОЙ) ---
@app.post("/check/")
async def check_answer_smart(request: CheckRequest):
    # 1. Ищем задачу
    task_id = request.task_id
    task = next((t for t in ALL_TASKS if str(t.get("id")) == str(task_id)), None)
    
    if not task:
        return {"is_correct": False, "error": "Задача не найдена"}

    correct_answer = str(task.get("answer", ""))
    user_answer = request.user_answer
    topic_id = task.get("topic", "unknown") # Наша тема для статистики

    # 2. Проверка (Нормализация + Gemini)
    is_correct = False
    if normalize_math_text(user_answer) == normalize_math_text(correct_answer):
        is_correct = True
    else:
        # Если не совпало просто, спрашиваем ИИ
        try:
            prompt = f"Равны ли математически: '{correct_answer}' и '{user_answer}'? Верни строго JSON: {{\"is_correct\": true/false}}"
            output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
            res = "".join(output).lower()
            is_correct = "true" in res
        except Exception as e:
            logger.error(f"AI Error: {e}")
            is_correct = False

    # 3. СОХРАНЯЕМ СТАТИСТИКУ (Выявление пробелов)
    # Здесь мы пишем в лог, чтобы потом проанализировать
    # В идеале — сделать запись в БД (student_id, topic_id, is_correct)
    logger.info(f"📊 СТАТИСТИКА: Студент {request.student_id} | Тема {topic_id} | Верно: {is_correct}")
    
    # Можно добавить функцию записи в файл:
    with open("user_stats.log", "a") as f:
        f.write(f"{datetime.now()},{request.student_id},{topic_id},{is_correct}\n")

    return {
        "is_correct": is_correct,
        "topic": topic_id,
        "correct_was": correct_answer if not is_correct else None
    }

# Остальные маршруты (random_task, review и т.д.) оставляй как были в FastAPI...
        
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
