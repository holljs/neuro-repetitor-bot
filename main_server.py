import logging
import os
import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# --- Настройка ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeuroBrain")
load_dotenv()

if not os.getenv("REPLICATE_API_TOKEN"):
    logger.warning("⚠️ REPLICATE_API_TOKEN не найден! Нейросеть работать не будет.")

# --- Модели ---
class ExplainRequest(BaseModel):
    question: str # Текст вопроса (если есть)
    correct_answer: str # То, что мы вбили руками (например: 3)
    user_answer: str = "Нет ответа" # То, что ответил ученик
    image_url: Optional[str] = None # Ссылка на картинку или Base64

app = FastAPI(title="Neuro Repetitor Vision API")

@app.get("/")
async def root():
    return {"status": "online", "service": "Replicate Vision Integration"}

@app.post("/explain/")
async def explain_error(request: ExplainRequest):
    """Генерация объяснения через мультимодальную модель (LLaVA)"""
    try:
        # Формируем жесткий системный промпт
        prompt_text = (
            f"Роль: Ты профессиональный, дружелюбный репетитор ОГЭ по математике.\n"
            f"Задача: Ученик решил задачу с картинки неправильно. Найди его ошибку и пошагово объясни, как прийти к правильному ответу.\n"
            f"Текст вопроса (если есть): {request.question}\n"
            f"Официальный правильный ответ: {request.correct_answer}\n"
            f"Неправильный ответ ученика: {request.user_answer}\n\n"
            f"Объясняй по-русски, используй понятные школьнику термины и формат Markdown."
        )

        # Выбираем модель: llava-1.5-13b (отлично видит и недорогая)
        model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
        
        # Параметры для Vision модели
        input_data = {
            "prompt": prompt_text,
            "max_tokens": 800,
            "temperature": 0.5
        }
        
        # Если бот прислал картинку, добавляем её в запрос!
        if request.image_url:
            input_data["image"] = request.image_url

        logger.info("Отправляем запрос в LLaVA...")
        output = replicate.run(model_id, input=input_data)
        
        # LLaVA возвращает ответ в виде потока (генератора), собираем его
        explanation = "".join(output)
        
        return {"explanation": explanation}
        
    except Exception as e:
        logger.error(f"Replicate Vision Error: {e}")
        return {"explanation": f"⚠️ Ошибка нейросети: {str(e)}. (Правильный ответ: {request.correct_answer})"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
