import os
import logging
import base64
import random
import json
import re
from pathlib import Path

import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("NeuroRepetitor")

# Загрузка переменных окружения
load_dotenv()

# --- ЗАГРУЗКА БАЗЫ ЗАДАЧ ДЛЯ ВК ---
QUESTIONS_DIR = Path("questions")
DB_FILE = QUESTIONS_DIR / "oge_math.json"

try:
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        ALL_TASKS = json.load(f)
    logger.info(f"✅ База задач загружена в API: {len(ALL_TASKS)} шт.")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки базы: {e}")
    ALL_TASKS = []

# Критичные переменные
REQUIRED_ENV_VARS = ["REPLICATE_API_TOKEN", "SERVER_URL"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"❌ Missing required environment variables: {', '.join(missing_vars)}")

# Инициализация приложения
app = FastAPI(
    title="Neuro Repetitor Vision API",
    version="1.2.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Настройка CORS для работы из браузера ВК
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модель запроса для проверки ответа
class CheckRequest(BaseModel):
    user_answer: str
    image_url: str
    task_text: Optional[str] = None
    student_id: Optional[int] = None

    @field_validator("image_url")
    def is_base64(cls, v):
        try:
            if v.startswith('data:image'):
                v_clean = v.split('base64,')[1]
            else:
                v_clean = v
            base64.b64decode(v_clean, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid Base64 image: {str(e)}")
        return v

# --- НОВЫЙ КЛАСС ДЛЯ РАЗБОРА ОШИБОК ---
class ReviewRequest(BaseModel):
    user_answer: str
    image_url: str
    task_text: Optional[str] = None
    student_id: Optional[int] = None
    simplify: bool = False # Флаг "Объясни проще"

# --- МАРШРУТЫ ДЛЯ ВК (ФРОНТЕНД) ---
@app.get("/random_task/")
async def get_random_task(exam_type: str = "oge"):
    """Возвращает случайную задачу для фронтенда ВК (с самоочисткой битых)"""
    global ALL_TASKS
    
    if not ALL_TASKS:
        raise HTTPException(status_code=500, detail="База задач пуста")

    # Делаем до 10 попыток найти нормальную задачу
    for _ in range(10):
        if not ALL_TASKS:
            raise HTTPException(status_code=500, detail="База задач закончилась (все были битые)")
            
        task = random.choice(ALL_TASKS)
        task_id = task.get("id")
        image_path_str = task.get("img")
        
        if not image_path_str:
            # Если пути вообще нет, удаляем задачу из базы
            ALL_TASKS = [t for t in ALL_TASKS if str(t.get("id")) != str(task_id)]
            continue # Пробуем следующую
            
        image_path = Path(image_path_str)
        
        if not image_path.exists():
            # КАРТИНКА БИТАЯ! Удаляем задачу навсегда
            logger.warning(f"⚠️ Найдена битая задача {task_id}. Файл {image_path} не существует. Удаляем из базы!")
            ALL_TASKS = [t for t in ALL_TASKS if str(t.get("id")) != str(task_id)]
            
            # Сразу перезаписываем файл, чтобы не наткнуться на нее после рестарта
            try:
                with open(DB_FILE, 'w', encoding='utf-8') as f:
                    json.dump(ALL_TASKS, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f"Не удалось перезаписать базу при очистке: {e}")
                
            continue # Пробуем вытянуть следующую задачу!

        # Если мы дошли сюда, значит файл существует! Грузим его.
        try:
            with open(image_path, "rb") as image_file:
                raw_base64 = base64.b64encode(image_file.read()).decode("utf-8")
                image_data_uri = f"data:image/jpeg;base64,{raw_base64}"
                
            return {
                "id": task.get("id"),
                "text": task.get("question"),
                "image": image_data_uri
            }
        except Exception as e:
            logger.error(f"Ошибка при чтении файла {image_path}: {e}")
            ALL_TASKS = [t for t in ALL_TASKS if str(t.get("id")) != str(task_id)]
            continue

    # Если за 10 попыток не нашли нормальную (что вряд ли)
    raise HTTPException(status_code=404, detail="Слишком много битых задач подряд. Попробуйте еще раз.")
# --- ОСНОВНЫЕ МАРШРУТЫ (ПРОВЕРКА) ---

@app.get("/")
async def root():
    """Статус сервера"""
    return JSONResponse({
        "status": "online",
        "service": "Neuro-Repetitor API",
        "port": os.getenv("SERVER_PORT", "8080"),
        "timestamp": datetime.utcnow().isoformat()
    })

# ДОБАВЛЕННЫЕ КЛАССЫ (если вы их еще не добавили в начало файла, пусть будут здесь)
class ReportRequest(BaseModel):
    task_id: str

class ReviewRequest(BaseModel):
    user_answer: str
    image_url: str
    task_text: Optional[str] = None
    student_id: Optional[int] = None
    simplify: bool = False

# --- МАРШРУТ 1: УДАЛЕНИЕ ПЛОХОЙ ЗАДАЧИ ---
@app.post("/report_task/")
async def report_broken_task(request: ReportRequest):
    task_id = request.task_id
    
    # Просто логируем жалобу в файл, не трогая основную базу
    try:
        with open("reports.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()}: Жалоба на задачу ID {task_id}\n")
        
        logger.info(f"🚩 Получена жалоба на задачу {task_id}. Записано в reports.txt")
        return {"success": True, "message": "Спасибо! Мы проверим это задание."}
    except Exception as e:
        logger.error(f"Ошибка записи жалобы: {e}")
        return {"success": False, "error": "Internal error"}

# --- МАРШРУТ 2: БЫСТРАЯ ПРОВЕРКА (ДЛЯ ТЕСТА) ---
@app.post("/check/")
async def check_answer_fast(request: CheckRequest):
    """Только Да/Нет. Экономим время и токены во время теста."""
    if not os.getenv("REPLICATE_API_TOKEN"):
        raise HTTPException(status_code=500, detail="Replicate API token not configured")
        
    prompt_text = f"""Ты строгий проверяющий ОГЭ/ЕГЭ. 
    На картинке условие задачи. Ученик дал ответ: "{request.user_answer}".
    Внимательно реши задачу сам и сравни с ответом ученика.
    ВЫДАЙ ОТВЕТ СТРОГО В ФОРМАТЕ JSON. Никакого текста.
    Формат: {{ "is_correct": true }} или {{ "is_correct": false }}
    """
    
    try:
        model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
        final_image_url = request.image_url
        if not final_image_url.startswith("data:image"):
            final_image_url = f"data:image/jpeg;base64,{final_image_url}"
            
        input_data = {
            "image": final_image_url,
            "prompt": prompt_text,
            "max_tokens": 50, # МИНИМУМ токенов
            "temperature": 0.1
        }
        
        output = replicate.run(model_id, input=input_data, wait=True, timeout=60)
        raw_response = "".join(output).strip()
        
        json_match = re.search(r'\{.*?\}', raw_response, re.DOTALL)
        if json_match:
            ai_verdict = json.loads(json_match.group(0))
        else:
            ai_verdict = {"is_correct": "true" in raw_response.lower()}
            
        if request.student_id:
            await save_task_result(request.student_id, request.user_answer, ai_verdict)
            
        return ai_verdict
        
    except Exception as e:
        logger.error(f"🚨 Fast Check Error: {e}")
        return {"is_correct": False, "error": str(e)}

# 1. МАРШРУТ ДЛЯ НАЧАЛА ТЕСТА (Списываем 3 кредита)
@app.post("/start_test_payment/")
async def pay_for_test(request: ReportRequest): # Используем тот же класс с task_id или student_id
    student_id = request.task_id # Допустим, передаем ID ученика
    balance = db.get_balance(student_id)
    
    if balance < 3:
        return {"success": False, "error": "Недостаточно кредитов"}
    
    db.update_balance(student_id, -3)
    return {"success": True, "new_balance": balance - 3}

# 2. МАРШРУТ РАЗБОРА (Теперь БЕСПЛАТНЫЙ на Flash модели)
@app.post("/review/")
async def review_answer_detailed(request: ReviewRequest):
    # Используем супер-дешевый Flash из твоих документов
    model_id = "google/gemini-3-flash" # [cite: 100]
    
    # Промпт оставляем, но списание кредитов УБИРАЕМ
    prompt_text = f"Ты ИИ-репетитор. Ученик ошибся в задаче. Объясни решение..."

    # 2. ВЫБОР МОДЕЛИ: Переходим на Flash (в 4-10 раз дешевле Pro!)
    # Согласно твоим докам: $0.50 за 1 млн входных токенов
    model_id = "google/gemini-3-flash" # 

    if request.simplify:
        prompt_text = f"На картинке задание. Ученик ответил: '{request.user_answer}'. Объясни решение максимально просто, 'на яблоках'."
    else:
        prompt_text = f"Ты репетитор. На картинке задача. Ученик ошибся, ответив '{request.user_answer}'. Напиши пошаговое верное решение."

    try:
        final_image_url = request.image_url
        if not final_image_url.startswith("data:image"):
            final_image_url = f"data:image/jpeg;base64,{final_image_url}"

        # Запускаем экономную модель Flash
        output = replicate.run(
            model_id,
            input={
                "images": [final_image_url],
                "prompt": prompt_text,
                "temperature": 0.7,
                "max_output_tokens": 1000
            }
        )
        
        explanation_text = "".join(output).strip()
        return {"explanation": explanation_text}
        
    except Exception as e:
        logger.error(f"🚨 Flash Review Error: {e}")
        return {"explanation": "Извини, нейросеть сейчас занята, попробуй через минуту."}
