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
app = FastAPI(title="Neuro Repetitor API", version="2.0.0")

# --- СЛОВАРЬ ТЕМ ---
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
    "chemistry_part1": "🧪 Химия (Часть 1)",
    # Физика
    "physics_part1": "⚡ Физика (Часть 1)",
    # География
    "geography_part1": "🌍 География (Часть 1)"
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

# --- БАЗЫ ДАННЫХ И ПРОГРЕСС ---
QUESTIONS_DIR = Path("questions")
PROGRESS_FILE = Path("user_progress.json")

DATABASES = {
    "oge_math": [],
    "oge_english": [],
    "oge_russian": [],
    "oge_chemistry": [],
    "oge_physics": [],
    "oge_geography": []  # Добавили Географию
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

# Загружаем все предметы
load_database("oge_math.json", "oge_math")
load_database("oge_english.json", "oge_english")
load_database("oge_russian.json", "oge_russian")
load_database("oge_chemistry.json", "oge_chemistry")
load_database("oge_physics.json", "oge_physics")
load_database("oge_geography.json", "oge_geography") # Загрузка базы Географии

# --- ЛОГИКА АНТИ-ПОВТОРА ---
def get_user_progress(user_id: str):
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get(str(user_id), [])
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

def normalize_text(text: str):
    if not text: return ""
    text = text.lower().replace(" ", "").replace(",", ".")
    text = re.sub(r'[\u2012\u2013\u2014\u2212]', '-', text)
    return text.strip()

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
    test_mode: str = "standard" # Добавили выбор режима (standard / pro)

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
    test_mode = request.test_mode
    ADMIN_IDS = ["54451631", "12345678"] 
    
    # Логика стоимости в КРЕДИТАХ: 3 за стандарт, 4 за профи
    cost = 4 if test_mode == "pro" else 3
    
    if str(student_id) in ADMIN_IDS:
        return {"success": True, "new_balance": "unlimited", "message": "Admin bypass", "cost": 0}
    
    # Здесь в будущем будет списываться стоимость из БД пользователя
    return {"success": True, "new_balance": 100 - cost, "cost": cost}
    
@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge_math", student_id: str = "guest"):
    db = DATABASES.get(exam_type, [])
    if not db: 
        raise HTTPException(status_code=500, detail=f"База для предмета {exam_type} пуста")
    
    # Фильтруем решенные задачи
    solved_ids = get_user_progress(student_id)
    available_tasks = [t for t in db if str(t.get("id")) not in solved_ids]
    
    if not available_tasks:
        return {
            "id": "done",
            "topic": "done",
            "text": "🎉 Поздравляем! Ты решил все доступные задачи по этому предмету. Скоро мы добавим новые!",
            "image": "",
            "answer": "---",
            "done": True
        }
    
    task = random.choice(available_tasks)
    img_path = task.get("image", "")
    
    if img_path and not img_path.startswith("http"):
        clean_name = img_path.split('/')[-1]
        topic = task.get("topic", "topic_01")

        if exam_type == "oge_physics":
            img_path = f"questions/images_oge_physics/{clean_name}"
        elif exam_type == "oge_chemistry":
            img_path = f"questions/images_oge_chemistry/{clean_name}"
        elif exam_type == "oge_geography": # Путь для Географии
            img_path = f"questions/images_oge_geography/{clean_name}"
        else:
            img_path = f"questions/images_oge_math/{topic}/{clean_name}"

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

    # Если ответ верный, записываем задачу в "решенные", чтобы она больше не выпадала
    if is_correct and request.student_id and str(request.student_id) != "guest":
        save_user_progress(request.student_id, request.task_id)

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
