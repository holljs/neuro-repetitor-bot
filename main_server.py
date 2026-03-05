import os
import logging
import base64
import json
import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from fastapi.responses import JSONResponse

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("NeuroRepetitor")

# Загрузка переменных окружения (с проверкой)
load_dotenv()

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

# Модель запроса
class CheckRequest(BaseModel):
    user_answer: str
    image_url: str
    student_id: Optional[int] = None  # Для сохранения статистики

    @validator("image_url")
    def is_base64(cls, v):
        try:
            base64.b64decode(v, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid Base64 image: {str(e)}")
        return v

# Основные маршруты
@app.get("/")
async def root():
    """Статус сервера"""
    return JSONResponse({
        "status": "online",
        "service": "Neuro-Repetitor API",
        "port": os.getenv("SERVER_PORT", "8002"),
        "timestamp": datetime.utcnow().isoformat()
    })

@app.post("/check/")
async def check_answer_vision(request: CheckRequest):
    """Проверка ответа через LLaVA с сохранением статистики"""
    # Проверка доступности Replicate
    if not os.getenv("REPLICATE_API_TOKEN"):
        raise HTTPException(
            status_code=500,
            detail="Replicate API token not configured"
        )

    # Подготовка промпта
    prompt_text = f"""
    Ты — строгий ЕГЭ/ОГЭ-репетитор по математике.
    Задание: [ТУТ БУДЕТ ТЕКСТ С КАРТИНКИ].
    Ученик дал ответ: "{request.user_answer}".
    Вердикт в формате JSON:
    {{
    "is_correct": true/false,
    "explanation": "Пошаговое решение и объяснение ошибки"
    }}
    """

    # Запрос к Replicate
    try:
        logger.info("🚀 Отправляем задачу на проверку в LLaVA...")
        model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
        
        input_data = {
            "image": request.image_url,
            "prompt": prompt_text,
            "max_tokens": 800,
            "temperature": 0.2
        }
        
        # Выполнение запроса с таймаутом
        output = replicate.run(
            model_id,
            input=input_data,
            wait=True,
            timeout=300
        )
        raw_response = "".join(output).strip()

        # Обработка формата ответа
        if raw_response.startswith("```json"):
            raw_response = raw_response.replace("```json", "").replace("```", "").strip()
        elif raw_response.startswith("```"):
            raw_response = raw_response.replace("```", "").strip()

        # Парсинг JSON
        try:
            ai_verdict = json.loads(raw_response)
        except json.JSONDecodeError:
            ai_verdict = {
                "is_correct": False,
                "explanation": raw_response
            }

        # Сохранение статистики (если указан student_id)
        if request.student_id:
            await save_task_result(request.student_id, request.user_answer, ai_verdict)

        return ai_verdict

    except replicate.ReplicateError as e:
        logger.error(f"💥 Replicate Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Replicate API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"🚨 Unexpected Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

# Вспомогательные функции
async def save_task_result(student_id: int, user_answer: str, ai_verdict: dict):
    """Сохранение результата в базу данных"""
    try:
        # Здесь должна быть реализация сохранения в БД
        # Например, через SQLAlchemy или Databases
        logger.info(f"💾 Сохранение результата для ученика {student_id}")
        # Примерный код:
        # await database.execute(
        #     "INSERT INTO tasks ...",
        #     {"student_id": student_id, ...}
        # )
    except Exception as e:
        logger.error(f"💥 Ошибка сохранения: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,  # Новый порт
        workers=2
    )

