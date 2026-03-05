import os
import logging
import base64
import json
import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from typing import Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("NeuroRepetitor")

# Загрузка переменных окружения
load_dotenv()
if not os.getenv("REPLICATE_API_TOKEN"):
    raise RuntimeError("❌ REPLICATE_API_TOKEN not found in environment variables")

# Инициализация приложения
app = FastAPI(
    title="Neuro Repetitor Vision API",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Модель запроса
class CheckRequest(BaseModel):
    user_answer: str
    image_url: str

    @validator("image_url")
    def is_base64(cls, v):
        try:
            base64.b64decode(v)
        except:
            raise ValueError("Invalid Base64 image")
        return v

# Основные маршруты
@app.get("/")
async def root():
    """Статус сервера"""
    return {"status": "online", "service": "Neuro-Repetitor API", "port": 8003}

@app.post("/check/")
async def check_answer_vision(request: CheckRequest):
    """Проверка ответа через LLaVA"""
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
    
    model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
    input_data = {
        "image": request.image_url,
        "prompt": prompt_text,
        "max_tokens": 800,
        "temperature": 0.2
    }

    try:
        logger.info("🚀 Отправляем задачу на проверку в LLaVA...")
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

if __name__ == "__main__":
    import uvicorn
    logger.info("🌐 Запускаем сервер на порту 8003")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8003,
        workers=2
    )
