import os
import json
import base64
import replicate
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
os.environ["REPLICATE_API_TOKEN"] = os.getenv("REPLICATE_API_TOKEN")

def crop_image(image_path, box, output_name):
    """Вырезает область из картинки по координатам 0-1000"""
    with Image.open(image_path) as img:
        w, h = img.size
        ymin, xmin, ymax, xmax = box
        left = xmin * w / 1000
        top = ymin * h / 1000
        right = xmax * w / 1000
        bottom = ymax * h / 1000
        
        # Вырезаем с небольшим запасом
        cropped = img.crop((max(0, left-5), max(0, top-5), min(w, right+5), min(h, bottom+5)))
        cropped.save(output_name, quality=95)
        return output_name

def process_smart_task(topic, p1, p2=None):
    """ИИ анализирует страницу и режет задачи"""
    base_path = f"questions/images_oge_math/{topic}"
    img1_path = f"{base_path}/page_{p1}.jpg"
    
    with open(img1_path, "rb") as f:
        img1_data = base64.b64encode(f.read()).decode("utf-8")
    
    images = [f"data:image/jpeg;base64,{img1_data}"]
    prompt = f"Найди все задачи на странице {p1}. Для каждой задачи верни JSON список: " \
             "{'number': 'номер', 'box_2d': [ymin, xmin, ymax, xmax]}"

    # Если передана вторая страница (с рисунками)
    if p2:
        img2_path = f"{base_path}/page_{p2}.jpg"
        with open(img2_path, "rb") as f:
            img2_data = base64.b64encode(f.read()).decode("utf-8")
        images.append(f"data:image/jpeg;base64,{img2_data}")
        prompt += f" Также проверь, нет ли на странице {p2} рисунков к этим задачам."

    print(f"⏳ ИИ анализирует страницу {p1}...")
    output = replicate.run("google/gemini-3-flash", input={"images": images, "prompt": prompt})
    
    try:
        # Улучшенная очистка ответа ИИ от лишнего текста
        full_text = "".join(output)
        if "```json" in full_text:
            clean_output = full_text.split("```json")[1].split("```")[0].strip()
        elif "```" in full_text:
            clean_output = full_text.split("```")[1].split("```")[0].strip()
        else:
            # Ищем начало массива [ и конец ]
            start = full_text.find("[")
            end = full_text.rfind("]") + 1
            clean_output = full_text[start:end]
            
        tasks = json.loads(clean_output)
        
        for task in tasks:
            out_file = f"{base_path}/task_{task['number']}.jpg"
            crop_image(img1_path, task['box_2d'], out_file)
            print(f"✅ Успешно вырезана задача №{task['number']}")
            
    except Exception as e:
        print(f"❌ Ошибка парсинга ИИ: {e}\nОтвет ИИ: {output}")

if __name__ == "__main__":
    # Указываем папку темы и страницы, которые нужно обработать
    topic = "topic_01_models"
    
    # Давай для начала нарежем страницы с 20 по 22
    for page_num in range(20, 23):
        # Если это 20-я страница, передаем 21-ю как контекст для рисунков
        context_page = 21 if page_num == 20 else None
        
        process_smart_task(topic, page_num, context_page)
