import logging
import os
import replicate
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

# --- Настройка ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeuroBrain")
load_dotenv()

if not os.getenv("REPLICATE_API_TOKEN"):
    logger.warning("⚠️ REPLICATE_API_TOKEN не найден!")

app = FastAPI(title="Neuro Repetitor Vision API")

class CheckRequest(BaseModel):
    user_answer: str # Ответ ученика
    image_url: str # Картинка задания в Base64

@app.get("/")
async def root():
    return {"status": "online", "service": "Replicate Vision Examiner"}

@app.post("/check/")
async def check_answer_vision(request: CheckRequest):
    """Отправляем картинку в LLaVA для решения и проверки ответа ученика"""
    try:
        # Супер-промпт, который заставляет нейросеть думать и выдавать структурированный ответ
        prompt_text = f"""
Ты — строгий, но справедливый репетитор ЕГЭ/ОГЭ по математике.
Я прикрепил картинку с заданием. 
Ученик решил эту задачу и дал ответ: "{request.user_answer}".

Твоя задача:
1. Внимательно прочитай и реши задачу с картинки сам.
2. Сравни свой правильный ответ с ответом ученика.
3. ВЫДАЙ ОТВЕТ СТРОГО В ФОРМАТЕ JSON:
{{
  "is_correct": true/false,
  "explanation": "Тут напиши пошаговое решение и объясни ошибку ученика (если она есть) по-русски."
}}

Отвечай ТОЛЬКО JSON-ом, без лишнего текста!
"""

        # Используем мощную и дешевую модель LLaVA-1.5 на Replicate
        model_id = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
        
        input_data = {
            "image": request.image_url,
            "prompt": prompt_text,
            "max_tokens": 800,
            "temperature": 0.2 # Низкая температура для точности математики
        }

        logger.info("Отправляем задачу на проверку в LLaVA...")
        output = replicate.run(model_id, input=input_data)
        
        # Собираем ответ
        raw_response = "".join(output).strip()
        
        # Нейросеть иногда добавляет Markdown-кавычки ```json ... ```
        if raw_response.startswith("```json"):
            raw_response = raw_response.replace("```json", "").replace("```", "").strip()
        elif raw_response.startswith("```"):
            raw_response = raw_response.replace("```", "").strip()

        # Пытаемся распарсить ответ нейросети как JSON
        try:
            ai_verdict = json.loads(raw_response)
        except json.JSONDecodeError:
            # Если нейросеть забыла про JSON и ответила просто текстом,
            # считаем это за объяснение
            ai_verdict = {
                "is_correct": False,
                "explanation": raw_response
            }
            
        return ai_verdict
        
    except Exception as e:
        logger.error(f"Replicate Vision Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
