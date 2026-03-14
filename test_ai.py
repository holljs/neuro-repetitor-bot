import os
import replicate
import json
import base64
from pathlib import Path

# Твой путь к уже нарезанной странице
PAGE_PATH = "questions/images_oge_math/topic_01_models/page_20.jpg"

def test_smart_crop():
    with open(PAGE_PATH, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")

    prompt = """
    На этой странице (стр 20) представлена задача про листы бумаги (форматы А). 
    1. Найди границы всей задачи целиком (текст + таблица).
    2. Верни JSON: {"number": "1", "box_2d": [ymin, xmin, ymax, xmax]} 
    Координаты от 0 до 1000.
    """

   model = "yorickvp/llava-13b:b5f6212d032508382d61ff00469ddda3e32fd8a0e75dc39d8a4191bb742157fb"
    
    # И заменим 'image' на 'image', как требует эта модель
    output = replicate.run(model, input={
        "image": f"data:image/jpeg;base64,{img_data}",
        "prompt": prompt,
        "top_p": 1,
        "temperature": 0.2
    })
    
    print("🤖 Ответ ИИ:", "".join(output))

if __name__ == "__main__":
    test_smart_crop()
