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
    """Возвращает случайную задачу для фронтенда ВК (с картинкой в Base64)"""
    if not ALL_TASKS:
        raise HTTPException(status_code=500, detail="База задач пуста")
        
    task = random.choice(ALL_TASKS)
    image_path_str = task.get("img")
    
    if not image_path_str:
        raise HTTPException(status_code=500, detail="В задаче нет пути к картинке")
        
    image_path = Path(image_path_str)
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Файл картинки не найден на сервере")
        
    # Готовим картинку для браузера
    with open(image_path, "rb") as image_file:
        raw_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        # ИСПРАВЛЕНИЕ: Формат картинок в базе - JPEG
        image_data_uri = f"data:image/jpeg;base64,{raw_base64}"
        
    return {
        "id": task.get("id"),
        "text": task.get("question"),
        "image": image_data_uri
    }

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
    global ALL_TASKS
    task_id_to_remove = request.task_id
    
    original_length = len(ALL_TASKS)
    ALL_TASKS = [task for task in ALL_TASKS if str(task.get("id")) != str(task_id_to_remove)]
    
    if len(ALL_TASKS) < original_length:
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(ALL_TASKS, f, ensure_ascii=False, indent=4)
            logger.info(f"🗑️ Задача {task_id_to_remove} НАВСЕГДА удалена из базы (осталось {len(ALL_TASKS)}).")
            return {"success": True, "message": "Task removed"}
        except Exception as e:
            logger.error(f"Ошибка при перезаписи JSON файла: {e}")
            return {"success": False, "error": "Could not write to file"}
            
    return {"success": False, "message": "Task not found"}

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

# --- МАРШРУТ 3: ПОДРОБНЫЙ РАЗБОР ОШИБОК ---
@app.post("/review/")
async def review_answer_detailed(request: ReviewRequest):
    """Длинный текст. Вызывается только после окончания теста."""
    if not os.getenv("REPLICATE_API_TOKEN"):
        raise HTTPException(status_code=500, detail="Replicate API token not configured")
        
    if request.simplify:
        prompt_text = f"""На картинке задание ОГЭ/ЕГЭ. Ученик не понял стандартное решение. 
        Его неправильный ответ: "{request.user_answer}".
        Объясни, как решать эту задачу максимально простым языком, "на пальцах", для новичков. Приведи понятные примеры.
        Ответь просто текстом на русском языке (без JSON). Напиши правильный ответ в конце."""
    else:
        prompt_text = f"""Ты профессиональный репетитор. На картинке условие задачи. 
        Ученик дал НЕВЕРНЫЙ ответ: "{request.user_answer}".
        Напиши подробное пошаговое решение этой задачи на русском языке, опираясь на данные с картинки. Объясни, в чем именно ошибка ученика, и напиши правильный ответ.
        Ответь просто текстом (без JSON)."""
        
    try:
        logger.info(f"🚀 Отправляем задачу на РАЗБОР (Simplify: {request.simplify})...")
        model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
        
        final_image_url = request.image_url
        if not final_image_url.startswith("data:image"):
            final_image_url = f"data:image/jpeg;base64,{final_image_url}"
            
        input_data = {
            "image": final_image_url,
            "prompt": prompt_text,
            "max_tokens": 1000, # Много токенов для объяснения
            "temperature": 0.4
        }
        
        output = replicate.run(model_id, input=input_data, wait=True, timeout=300)
        explanation_text = "".join(output).strip()
        
        return {"explanation": explanation_text}
        
    except Exception as e:
        logger.error(f"🚨 Review Error: {e}")
        return {"explanation": "Извини, сервер перегружен, не могу написать объяснение прямо сейчас."}

async def save_task_result(student_id: int, user_answer: str, ai_verdict: dict):
    try:
        logger.info(f"💾 Сохранение результата для ученика {student_id}")
    except Exception as e:
        logger.error(f"💥 Ошибка сохранения: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_server:app", host="0.0.0.0", port=8080, workers=2)





