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
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse # Для красивой админки

# --- ИНИЦИАЛИЗАЦИЯ ---
load_dotenv()
app = FastAPI(title="Neuro Repetitor API", version="1.4.0")

# РАЗРЕШАЕМ КАРТИНКИ
if Path("questions").exists():
    app.mount("/questions", StaticFiles(directory="questions"), name="questions")

# НАСТРОЙКА CORS
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

# --- МАРШРУТЫ ---

@app.get("/")
async def root():
    return {"status": "online", "server_time": datetime.utcnow().isoformat()}

@app.post("/start_test_payment/")
async def pay_for_test(request: ReportRequest):
    student_id = request.student_id
    ADMIN_IDS = [54451631, 12345678] # Твой ID здесь
    if student_id in ADMIN_IDS:
        return {"success": True, "new_balance": "unlimited"}
    return {"success": True, "new_balance": 100}

@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge_math"):
    if not ALL_TASKS: raise HTTPException(status_code=500, detail="База пуста")
    task = random.choice(ALL_TASKS)
    return {
        "id": task.get("id", "unknown"),
        "topic": task.get("topic", "Общая тема"),
        "text": task.get("text", ""),
        "image": task.get("image", ""),
        "answer": task.get("answer", "")
    }

@app.post("/check/")
async def check_answer_smart(request: CheckRequest):
    task = next((t for t in ALL_TASKS if str(t.get("id")) == str(request.task_id)), None)
    if not task: return {"is_correct": False, "error": "Задача не найдена"}

    correct_answer = str(task.get("answer", ""))
    is_correct = normalize_math_text(request.user_answer) == normalize_math_text(correct_answer)
    
    if not is_correct and correct_answer != "---":
        try:
            prompt = f"Равны ли математически: '{correct_answer}' и '{request.user_answer}'? Верни строго JSON: {{\"is_correct\": true/false}}"
            output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
            is_correct = "true" in "".join(output).lower()
        except: is_correct = False

    # ЗАПИСЬ СТАТИСТИКИ
    with open("user_stats.log", "a") as f:
        f.write(f"{datetime.now()},{request.student_id},{task.get('topic','unknown')},{is_correct}\n")

    return {"is_correct": is_correct, "topic": task.get("topic"), "correct_was": correct_answer if not is_correct else None}

# --- АДМИН-ПАНЕЛЬ (НОВОЕ!) ---

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(key: str = Query(None)):
    if key != "super-repetitor-2026": # Твой секретный пароль в ссылке
        return "<h1>Доступ закрыт</h1>"
    
    stats = {}
    if os.path.exists("user_stats.log"):
        with open("user_stats.log", "r") as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 4:
                    topic, res = parts[2], parts[3] == "True"
                    if topic not in stats: stats[topic] = {"ok": 0, "err": 0}
                    if res: stats[topic]["ok"] += 1
                    else: stats[topic]["err"] += 1

    # Генерируем простую HTML таблицу
    rows = "".join([f"<tr><td>{t}</td><td>{d['ok']}</td><td>{d['err']}</td><td>{round(d['ok']/(d['ok']+d['err'])*100)}%</td></tr>" for t, d in stats.items()])
    
    return f"""
    <html>
        <head><title>Админка</title><style>table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ddd;padding:8px;text-align:left}} tr:nth-child(even){{background:#f2f2f2}}</style></head>
        <body>
            <h1>📊 Аналитика пробелов по темам</h1>
            <table><tr><th>Тема</th><th>Верно</th><th>Ошибок</th><th>Успешность</th></tr>{rows}</table>
        </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
