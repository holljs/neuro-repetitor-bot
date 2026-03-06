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
            # Если пришел data URI, отрезаем префикс для проверки
            if v.startswith('data:image'):
                v_clean = v.split('base64,')[1]
            else:
                v_clean = v
            base64.b64decode(v_clean, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid Base64 image: {str(e)}")
        return v

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
        image_data_uri = f"data:image/png;base64,{raw_base64}"
        
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

@app.post("/check/")
async def check_answer_vision(request: CheckRequest):
    """Проверка ответа через LLaVA"""
    if not os.getenv("REPLICATE_API_TOKEN"):
        raise HTTPException(status_code=500, detail="Replicate API token not configured")

     prompt_text = f"""
    Ты — профессиональный и доброжелательный репетитор ОГЭ/ЕГЭ.
    
    Вводные данные:
    - Номер задания: {request.task_text}
    - Ответ ученика: "{request.user_answer}"
    
    Твоя задача:
    1. Главное условие задачи, все графики, формулы и числа находятся ТОЛЬКО НА КАРТИНКЕ. Внимательно изучи картинку.
    2. Пойми по картинке, к какому предмету (Математика, Физика и т.д.) относится задача, и реши её по шагам самостоятельно.
    3. Сравни свой правильный ответ с ответом ученика.

    ВЫДАЙ ОТВЕТ СТРОГО В ФОРМАТЕ JSON. Никакого текста до или после скобок {{ }}.
    Формат ответа:
    {{
      "is_correct": true (если ответ совпал) или false (если есть ошибка),
      "explanation": "Здесь напиши подробное пошаговое решение на русском языке, опираясь на данные с картинки. Обязательно напиши правильный ответ. Если ученик ошибся, объясни, в чем именно его ошибка."
    }}
    """

    try:
        logger.info("🚀 Отправляем задачу на проверку в LLaVA...")
        model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
        
        final_image_url = request.image_url
        if final_image_url and not final_image_url.startswith("data:image"):
            final_image_url = f"data:image/png;base64,{final_image_url}"

        input_data = {
            "image": final_image_url,
            "prompt": prompt_text,
            "max_tokens": 800,
            "temperature": 0.2
        }
        
        output = replicate.run(model_id, input=input_data, wait=True, timeout=300)
        raw_response = "".join(output).strip()

        # Очистка и парсинг
        raw_response = raw_response.replace("\\_", "_").replace("\\", "")
        json_match = re.search(r'\{.*?\}', raw_response, re.DOTALL)
        
        try:
            if json_match:
                clean_json_str = json_match.group(0)
                ai_verdict = json.loads(clean_json_str)
                tail_text = raw_response.replace(clean_json_str, "").strip()
                if tail_text and "explanation" in ai_verdict:
                    ai_verdict["explanation"] += f"\n\n(Дополнение ИИ: {tail_text})"
            else:
                ai_verdict = json.loads(raw_response)
        except Exception:
            clean_text = re.sub(r'["{}\[\]]', '', raw_response).replace('is_correct: false,', '').replace('explanation:', '').strip()
            ai_verdict = {
                "is_correct": False,
                "explanation": clean_text
            }

        if request.student_id:
            await save_task_result(request.student_id, request.user_answer, ai_verdict)

        return ai_verdict

    except Exception as e:
        logger.error(f"🚨 Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def save_task_result(student_id: int, user_answer: str, ai_verdict: dict):
    try:
        logger.info(f"💾 Сохранение результата для ученика {student_id}")
    except Exception as e:
        logger.error(f"💥 Ошибка сохранения: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_server:app", host="0.0.0.0", port=8080, workers=2)

