import os
import json
import base64
import replicate
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Настройки страниц с ответами (укажи свои)
ANSWER_PAGES_RANGE = range(229, 239) 

def get_task_coords_and_answers(page_image_path):
    """Просим ИИ найти задачи и ответы на странице"""
    with open(page_image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")
    
    prompt = """
    Проанализируй страницу учебника математики. 
    1. Найди каждую отдельную задачу.
    2. Для каждой задачи верни:
       - 'number': номер задачи (например, 139)
       - 'box': координаты [ymin, xmin, ymax, xmax] в процентах (0-1000)
       - 'text': краткое условие
       - 'extra_ref': если задача ссылается на рисунок на другой странице (например, 'рис 10 на стр 21'), напиши 'page_21'
    Верни строго JSON списком.
    """
    
    # Используем Gemini 1.5 Flash через Replicate
    model = "google/gemini-1.5-flash"
    output = replicate.run(model, input={
        "image": f"data:image/jpeg;base64,{img_data}",
        "prompt": prompt
    })
    
    return json.loads("".join(output))

def crop_and_save_task(page_img_path, task_data, topic_folder):
    """Вырезаем задачу и сохраняем"""
    img = Image.open(page_img_path)
    w, h = img.size
    
    # Конвертируем координаты из 0-1000 в пиксели
    ymin, xmin, ymax, xmax = task_data['box']
    left = xmin * w / 1000
    top = ymin * h / 1000
    right = xmax * w / 1000
    bottom = ymax * h / 1000
    
    # Вырезаем
    task_img = img.crop((left, top, right, bottom))
    
    output_path = Path(f"questions/images_oge_math/{topic_folder}/task_{task_data['number']}.jpg")
    task_img.save(output_path, quality=95)
    print(f"🎯 Вырезана задача №{task_data['number']}")

def run_ai_factory(topic_folder, pages):
    print(f"🚀 Запуск ИИ-фабрики для темы: {topic_folder}")
    for p in pages:
        page_img = f"questions/images_oge_math/{topic_folder}/page_{p}.jpg"
        if os.path.exists(page_img):
            tasks = get_task_coords_and_answers(page_img)
            for task in tasks:
                crop_and_save_task(page_img, task, topic_folder)

if __name__ == "__main__":
    # Пример: запускаем для темы "Вычисления"
    # run_ai_factory("topic_02_calc", range(31, 48))
    print("AI Cropper готов. Вызови run_ai_factory для нужной темы.")
