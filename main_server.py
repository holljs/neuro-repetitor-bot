import logging
import os
import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image
import io

# --- Настройка ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeuroBrain")
load_dotenv()

# --- Проверка токенов ---
if not os.getenv("REPLICATE_API_TOKEN"):
    logger.warning("⚠️ REPLICATE_API_TOKEN не найден! Нейросеть работать не будет.")

# --- Модели ---
class ExplainRequest(BaseModel):
    question: str
    correct_answer: str
    user_answer: str = "Нет ответа"

app = FastAPI(title="Neuro Repetitor Brain API", version="3.0.0 (Paid)")

@app.get("/")
async def root():
    return JSONResponse(content={"status": "online", "service": "Replicate Integration"})

@app.post("/explain/")
async def explain_error(request: ExplainRequest):
    """Генерация объяснения через Replicate (Llama-3)"""
    try:
        # Промпт для нейросети
        prompt_text = (
            f"Роль: Ты профессиональный репетитор ЕГЭ/ОГЭ.\n"
            f"Задача: Объясни ошибку ученика кратко и понятно.\n"
            f"Вопрос: {request.question}\n"
            f"Верный ответ: {request.correct_answer}\n"
            f"Ответ ученика: {request.user_answer}\n\n"
            f"Дай пошаговое объяснение решения. Используй Markdown."
        )

        output = replicate.run(
            "meta/meta-llama-3-8b-instruct",
            input={
                "prompt": prompt_text,
                "max_tokens": 600,
                "temperature": 0.6,
                "system_prompt": "Ты говоришь на русском языке."
            }
        )
        
        explanation = "".join(output)
        return {"explanation": explanation}

    except Exception as e:
        logger.error(f"Replicate Error: {e}")
        return {"explanation": f"⚠️ Ошибка нейросети: {str(e)}. Правильный ответ: {request.correct_answer}"}

# --- ЗАПУСК СЕРВЕРА ---
if __name__ == "__main__":
    import uvicorn
    # Запускаем FastAPI на порту 8002
    uvicorn.run(app, host="0.0.0.0", port=8002)

