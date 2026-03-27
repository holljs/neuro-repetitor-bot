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
from fastapi.responses import HTMLResponse

# --- ИНИЦИАЛИЗАЦИЯ ---
load_dotenv()
app = FastAPI(title="Neuro Repetitor API", version="1.7.0")

# --- СЛОВАРЬ ТЕМ (ДЛЯ АДМИНКИ И ЛОГОВ) ---
TOPIC_NAMES = {
    # Математика
    "topic_01": "🏠 Практические задачи",
    "topic_02": "🔢 Вычисления и дроби",
    "topic_03": "📏 Единицы измерения",
    "topic_04": "⚖️ Уравнения",
    "topic_04_eq": "⚖️ Уравнения",
    "topic_05": "📍 Координатная прямая",
    "topic_06": "📊 Графики и диаграммы",
    "topic_07": "📈 Графики функций",
    "topic_08": "🧩 Выражения",
    "topic_09": "🧪 Формулы",
    "topic_10": "🔢 Последовательности",
    # Английский
    "grammar": "📚 Грамматика (Англ)",
    "vocabulary": "📝 Лексика (Англ)",
    # Русский
    "syntax": "🏗️ Синтаксис",
    "punctuation": "✍️ Пунктуация",
    "orthography": "📝 Орфография",
    "lexis": "📖 Лексика и грамматика",
    # Химия
    "chemistry_part1": "🧪 Химия (Часть 1)",  # <--- ЗАПЯТАЯ!
    # Физика
    "physics_part1": "⚡ Физика (Часть 1)"
}

# РАЗРЕШАЕМ КАРТИНКИ
if Path("questions").exists():
    app.mount("/questions", StaticFiles(directory="questions"), name="questions")

# НАСТРОЙКА CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("NeuroRepetitor")

# --- ЗАГРУЗКА ВСЕХ БАЗ ДАННЫХ ---
QUESTIONS_DIR = Path("questions")
DATABASES = {
    "oge_math": [],
    "oge_english": [],
    "oge_russian": [],
    "oge_chemistry": [],
    "oge_physics": []
}

def load_database(filename, db_key):
    filepath = QUESTIONS_DIR / filename
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                DATABASES[db_key] = json.load(f)
            logger.info(f"✅ База {db_key} загружена: {len(DATABASES[db_key])} шт.")
        except Exception as e:
            logger.error(f"❌ Ошибка чтения JSON {filename}: {e}")
    else:
        logger.warning(f"⚠️ Файл {filename} не найден!")

# Загружаем предметы при старте (ТЕПЕРЬ ИХ ТРИ!)
load_database("oge_math.json", "oge_math")
load_database("oge_english.json", "oge_english")
load_database("oge_russian.json", "oge_russian")
load_database("oge_chemistry.json", "oge_chemistry")
load_database("oge_physics.json", "oge_physics")

def normalize_text(text: str):
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
    image_url: Optional[str] = None
    task_text: Optional[str] = None
    student_id: Optional[int] = None
    simplify: bool = False

class PaymentRequest(BaseModel):
    student_id: Optional[int] = None
    task_id: Optional[str] = None

# --- МАРШРУТЫ ---

@app.get("/")
async def root():
    return {"status": "online", "server_time": datetime.utcnow().isoformat()}

@app.get("/check_sub/{user_id}")
async def check_subscription(user_id: int):
    return {"subscription": "active"}

@app.post("/start_test_payment/")
async def pay_for_test(request: PaymentRequest):
    student_id = request.student_id
    ADMIN_IDS = [54451631, 12345678] 
    
    if student_id in ADMIN_IDS:
        return {"success": True, "new_balance": "unlimited", "message": "Admin bypass"}
    return {"success": True, "new_balance": 100}

@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge_math"):
    db = DATABASES.get(exam_type, [])
    if not db: 
        raise HTTPException(status_code=500, detail=f"База для предмета {exam_type} пуста")
    
    task = random.choice(db)
    
    img_path = task.get("image", "")
    if img_path and not img_path.startswith("http"):
        # Берем только имя файла (например, task_p100_11.jpg)
        clean_name = img_path.split('/')[-1] 
        
        task_id = str(task.get("id", ""))
        
        if "p" in task_id:
            # ДЛЯ ФИЗИКИ: файлы лежат сразу в папке предмета
            img_path = f"questions/images_oge_physics/{clean_name}"
        else:
            # ДЛЯ ОСТАЛЬНЫХ: используем структуру с папкой топика
            topic = task.get("topic", "topic_01")
            # Проверяем химию (c) или математику (по умолчанию)
            subject_folder = "images_oge_chemistry" if "c" in task_id else "images_oge_math"
            img_path = f"questions/{subject_folder}/{topic}/{clean_name}"
        
    return {
        "id": task.get("id", "unknown"),
        "topic": task.get("topic", "Общая тема"),
        "text": task.get("task_text", task.get("text", "")),
        "image": img_path,
        "answer": task.get("answer", "")
    }

@app.post("/check/")
async def check_answer_smart(request: CheckRequest):
    task = None
    for db in DATABASES.values():
        task = next((t for t in db if str(t.get("id")) == str(request.task_id)), None)
        if task: break

    if not task: return {"is_correct": False, "error": "Задача не найдена"}

    correct_answer = str(task.get("answer", ""))
    is_correct = normalize_text(request.user_answer) == normalize_text(correct_answer)
    
    if not is_correct and correct_answer != "---":
        try:
            prompt = f"Равны ли эти два ответа на тест (учитывай синонимы, опечатки или математическое равенство): '{correct_answer}' и '{request.user_answer}'? Верни строго JSON: {{\"is_correct\": true/false}}"
            output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
            is_correct = "true" in "".join(output).lower()
        except Exception as e: 
            logger.error(f"Ошибка проверки ИИ: {e}")
            is_correct = False

    with open("user_stats.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()},{request.student_id},{task.get('topic','unknown')},{is_correct}\n")

    return {"is_correct": is_correct, "topic": task.get("topic"), "correct_was": correct_answer if not is_correct else None}

@app.post("/review/")
async def explain_mistake(request: ReviewRequest):
    content = request.task_text if request.task_text else "Текст задачи не предоставлен"
    
    if request.simplify:
        prompt = (f"Объясни задачу максимально просто и понятно, 'на пальцах' (можно использовать примеры из жизни, если это уместно). "
                  f"Текст задачи: {content}. "
                  f"Ответ ученика: {request.user_answer}. "
                  f"Объясни, почему ответ ученика неверен и какое правило здесь работает.")
    else:
        prompt = (f"Напиши подробное пошаговое объяснение или решение задачи. "
                  f"Текст: {content}. "
                  f"Ответ ученика: {request.user_answer}. "
                  f"Укажи, на каком этапе ученик мог допустить ошибку и как правильно рассуждать.")

    input_data = {"prompt": prompt}
    if request.image_url:
        input_data["image"] = request.image_url

    try:
        output = replicate.run("google/gemini-3-flash", input=input_data)
        explanation = "".join(output)
        explanation = explanation.replace("\n", "<br>")
        return {"explanation": explanation}
    except Exception as e:
        logger.error(f"Ошибка ИИ при разборе: {e}")
        return {"explanation": "Извините, произошла ошибка при генерации разбора. Попробуйте еще раз."}

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(key: str = Query(None)):
    if key != "super-repetitor-2026":
        return "<h1>Доступ закрыт</h1>"
    
    stats = {}
    if os.path.exists("user_stats.log"):
        with open("user_stats.log", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    topic_code, res_str = parts[2], parts[3]
                    topic_name = TOPIC_NAMES.get(topic_code, topic_code)
                    res = (res_str == "True")
                    
                    if topic_name not in stats: stats[topic_name] = {"ok": 0, "err": 0}
                    if res: stats[topic_name]["ok"] += 1
                    else: stats[topic_name]["err"] += 1

    rows = "".join([f"<tr><td>{t}</td><td>{d['ok']}</td><td>{d['err']}</td><td>{round(d['ok']/(d['ok']+d['err'])*100)}%</td></tr>" for t, d in stats.items()])
    
    return f"""
    <html>
        <head>
            <title>Админка: Нейрорепетитор</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f9f9f9; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>📊 Аналитика пробелов по темам</h1>
            <table>
                <tr><th>Тема</th><th>Верно</th><th>Ошибок</th><th>Успешность</th></tr>
                {rows}
            </table>
        </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
