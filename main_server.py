import os
import logging
import base64
import json
import re
import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
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
    task_text: str = ""           # <--- Добавили текст задачи
    student_id: Optional[int] = None
    
    @field_validator("image_url")
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
    Текст задания: {request.task_text}.
    Внимательно изучи прикрепленную картинку, реши задачу по шагам и проверь ответ ученика: "{request.user_answer}".
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
        
       # Убеждаемся, что префикс есть
        final_image_url = request.image_url
        if final_image_url and not final_image_url.startswith("data:image"):
            final_image_url = f"data:image/png;base64,{final_image_url}"

        input_data = {
            "image": final_image_url,  # <--- Используем переменную с префиксом
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
        # Очищаем от случайных экранирований нейросети
        raw_response = raw_response.replace("\\_", "_").replace("\\", "")

        # Умный поиск JSON внутри любого текста (даже если нейросеть "наболтала" лишнего)
        import re
        json_match = re.search(r'\{.*?\}', raw_response, re.DOTALL)
        
        try:
            if json_match:
                clean_json_str = json_match.group(0)
                ai_verdict = json.loads(clean_json_str)
                
                # Если нейросеть добавила полезный текст ПОСЛЕ json, приклеим его к объяснению
                tail_text = raw_response.replace(clean_json_str, "").strip()
                if tail_text and "explanation" in ai_verdict:
                    ai_verdict["explanation"] += f"\n\n(Дополнение ИИ: {tail_text})"
            else:
                ai_verdict = json.loads(raw_response)
        except Exception:
            # Если JSON вообще сломан, отдаем как чистый текст, убрав мусор
            clean_text = re.sub(r'["{}\[\]]', '', raw_response).replace('is_correct: false,', '').replace('explanation:', '').strip()
            ai_verdict = {
                "is_correct": False,
                "explanation": clean_text
            }

        # Сохранение статистики (если указан student_id)
        if request.student_id:
            await save_task_result(request.student_id, request.user_answer, ai_verdict)

        return ai_verdict

    except Exception as e:  # <--- ЭТОТ БЛОК ОСТАВЛЯЕМ
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
        logger.info(f"💾 Сохранение результата для ученика {student_id}")
    except Exception as e:
        logger.error(f"💥 Ошибка сохранения: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_server:app",  # <--- Поставьте здесь кавычки и название файла!
        host="0.0.0.0",
        port=8080,
        workers=2
    )





