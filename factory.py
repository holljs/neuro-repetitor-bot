import os
import json
import base64
import fitz  # PyMuPDF
import replicate
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Настройки
PDF_PATH = "math_oge.pdf"
TASKS_CONFIG = [
    {"topic": "topic_01", "pages": range(8, 31)},  # Практические задачи
    {"topic": "topic_02", "pages": range(31, 50)}, # Вычисления
]

def get_page_as_jpg(pdf_path, page_num, output_path):
    doc = fitz.open(pdf_path)
    if page_num > len(doc): return False
    page = doc.load_page(page_num - 1)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
    pix.save(output_path)
    doc.close()
    return True

def smart_crop_and_stitch(topic, p1, p2=None):
    base_path = Path(f"questions/images_oge_math/{topic}")
    base_path.mkdir(parents=True, exist_ok=True)
    
    img1_path = base_path / f"page_{p1}.jpg"
    get_page_as_jpg(PDF_PATH, p1, img1_path)
    
    with open(img1_path, "rb") as f:
        img1_data = base64.b64encode(f.read()).decode("utf-8")
    
    images = [f"data:image/jpeg;base64,{img1_data}"]
    
    # --- УЛУЧШЕННЫЙ ПРОМПТ ---
    prompt = (
        f"Ты — эксперт по оцифровке ОГЭ. Страница {p1}.\n"
        "ЗАДАЧА: Извлеки текст задач. Если задаче нужна схема/таблица, дай координаты.\n\n"
        "ПРАВИЛА:\n"
        "1. 'has_visual': true ТОЛЬКО если без картинки задачу НЕ РЕШИТЬ.\n"
        "2. Если картинка/таблица к задаче находится на ТЕКУЩЕЙ странице, дай координаты в 'box_2d'.\n"
    )

    if p2:
        img2_path = base_path / f"page_{p2}.jpg"
        if get_page_as_jpg(PDF_PATH, p2, img2_path):
            with open(img2_path, "rb") as f:
                img2_data = base64.b64encode(f.read()).decode("utf-8")
            images.append(f"data:image/jpeg;base64,{img2_data}")
            prompt += (
                f"3. ВАЖНО: Если текст задачи на стр {p1}, а схема/таблица к ней на стр {p2}, "
                "установи 'needs_stitch': true и дай координаты картинки со второй страницы в 'stitch_box'.\n"
            )

    prompt += (
        "\nВерни JSON список:\n"
        "[ {'number': '1', 'task_text': 'текст', 'has_visual': true, 'box_2d': [ymin, xmin, ymax, xmax], "
        "'needs_stitch': true/false, 'stitch_box': [ymin, xmin, ymax, xmax]} ]"
    )

    print(f"🧠 ИИ анализирует {topic} (стр {p1})...")
    try:
        output = replicate.run("google/gemini-3-flash", input={"images": images, "prompt": prompt})
        clean_text = "".join(output).replace("```json", "").replace("```", "").strip()
        tasks = json.loads(clean_text)
        
        with Image.open(img1_path) as main_img:
            w, h = main_img.size
            for t in tasks:
                img_filename = f"task_{t.get('number')}.jpg"
                save_path = base_path / img_filename
                
                # Логика нарезки и склейки
                if t.get('has_visual'):
                    # Режем основной кусок
                    y0, x0, y1, x1 = [c * h / 1000 if i%2==0 else c * w / 1000 for i, c in enumerate(t.get('box_2d', [0,0,0,0]))]
                    # Если координат нет, но визуализация нужна — берем всю страницу или пропускаем
                    task_part = main_img.crop((x0, y0, x1, y1)) if t.get('box_2d') != [0,0,0,0] else main_img

                    # Склеиваем со второй страницей, если ИИ сказал
                    if t.get('needs_stitch') and p2 and 'stitch_box' in t:
                        with Image.open(img2_path) as side_img:
                            sw, sh = side_img.size
                            sy0, sx0, sy1, sx1 = [c * sh / 1000 if i%2==0 else c * sw / 1000 for i, c in enumerate(t['stitch_box'])]
                            stitch_part = side_img.crop((sx0, sy0, sx1, sy1))
                            
                            # Склейка по вертикали
                            new_img = Image.new('RGB', (max(task_part.width, stitch_part.width), task_part.height + stitch_part.height + 10), (255,255,255))
                            new_img.paste(task_part, (0, 0))
                            new_img.paste(stitch_part, (0, task_part.height + 10))
                            task_part = new_img

                    task_part.save(save_path, quality=95)
                    # !!! ВАЖНО: Прописываем путь к картинке в JSON задачи !!!
                    t['image'] = f"questions/images_oge_math/{topic}/{img_filename}"
                    print(f"🖼️ Создана склейка для №{t['number']}")
                else:
                    t['image'] = "" # Картинка не нужна

        # Сохраняем JSON страницы (теперь с путями к картинкам!)
        with open(base_path / f"data_page_{p1}.json", "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=4)

    except Exception as e:
        print(f"⚠️ Ошибка: {e}")

if __name__ == "__main__":
    # Очистка перед запуском (опционально)
    # os.system("rm -rf questions/images_oge_math/*")
    for config in TASKS_CONFIG:
        for p in config['pages']:
            smart_crop_and_stitch(config['topic'], p, p + 1)
