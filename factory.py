import os
import json
import base64
import fitz  # PyMuPDF
import replicate
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
os.environ["REPLICATE_API_TOKEN"] = os.getenv("REPLICATE_API_TOKEN")

# ==========================================
# ТАБЛИЦА ТЕМ (Меняй только здесь!)
# ==========================================
TASKS_CONFIG = [
   # {"topic": "topic_01_models", "pages": range(8, 31)},      # Практические задачи
   # {"topic": "topic_02_calc",   "pages": range(31, 50)},     # Вычисления
   # {"topic": "topic_03_units",  "pages": range(50, 61)},     # Единицы измерения
    {"topic": "topic_04_eq",     "pages": range(61, 72)},     # Уравнения
   # {"topic": "topic_05_line",   "pages": range(72, 90)},     # Координатная прямая
   # {"topic": "topic_06_charts", "pages": range(90, 107)},    # Графики и диаграммы
   # {"topic": "topic_07_funcs",  "pages": range(107, 127)},   # Графики функций
   # {"topic": "topic_08_expr",   "pages": range(127, 134)},   # Выражения
   # {"topic": "topic_09_form",   "pages": range(134, 143)},   # Формулы
   # {"topic": "topic_10_seq",    "pages": range(143, 149)},   # Последовательности
]

PDF_PATH = "math_oge.pdf" # Проверь имя файла!

# ==========================================
# ЛОГИКА ФАБРИКИ (Тут менять ничего не надо)
# ==========================================

def get_page_as_jpg(pdf_path, page_num, output_path):
    """Превращает страницу PDF в лист JPG"""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num - 1)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
    pix.save(output_path)
    doc.close()

def smart_crop_and_stitch(topic, p1, p2=None):
    """ИИ режет и склеивает рисунки"""
    base_path = Path(f"questions/images_oge_math/{topic}")
    base_path.mkdir(parents=True, exist_ok=True)
    
    img1_path = base_path / f"page_{p1}.jpg"
    get_page_as_jpg(PDF_PATH, p1, img1_path)
    
    with open(img1_path, "rb") as f:
        img1_data = base64.b64encode(f.read()).decode("utf-8")
    
    images = [f"data:image/jpeg;base64,{img1_data}"]
    
    # Теперь промпт с правильными отступами и нужной переменной page_num (заменили на p1)
    prompt = (
        f"Ты — эксперт по оцифровке учебников математики. Оцифруй страницу {p1}.\n"
        "ГЛАВНОЕ: Мы переходим на текстовый формат задач.\n\n"
        "ИНСТРУКЦИЯ:\n"
        "1. Извлеки текст каждой задачи полностью (включая инструкции типа 'Решите уравнение').\n"
        "2. Если задача содержит график, чертеж или таблицу (то, что нельзя передать текстом), "
        "установи 'has_visual': true и дай координаты ЭТОГО РИСУНКА в 'box_2d'.\n"
        "3. Если в задаче ТОЛЬКО текст и формулы, установи 'has_visual': false и 'box_2d': [0,0,0,0].\n"
        "4. Формулы пиши в простом текстовом виде (например, x^2 + 3x - 4 = 0).\n\n"
        "Верни СТРОГО JSON список: "
        "[{'number': 'номер', 'task_text': 'текст задачи', 'has_visual': true/false, 'box_2d': [ymin, xmin, ymax, xmax]}]"
    )

    if p2:
        img2_path = base_path / f"page_{p2}.jpg"
        get_page_as_jpg(PDF_PATH, p2, img2_path)
        with open(img2_path, "rb") as f:
            img2_data = base64.b64encode(f.read()).decode("utf-8")
        images.append(f"data:image/jpeg;base64,{img2_data}")
        prompt += f" Если задаче нужен рисунок со стр {p2}, добавь 'stitch_box': [ymin, xmin, ymax, xmax] для рисунка."

    print(f"🧠 ИИ анализирует {topic} (стр {p1})...")
    output = replicate.run("google/gemini-3-flash", input={"images": images, "prompt": prompt})
    
    try:
        clean_text = "".join(output).replace("```json", "").replace("```", "").strip()
        tasks = json.loads(clean_text)
        
        with Image.open(img1_path) as main_img:
            w, h = main_img.size
            for t in tasks:
                # 1. Сначала сохраняем текст в отдельный лог/базу (опционально для отладки)
                print(f"📝 Обработка задачи {t.get('number')}: {t.get('task_text')[:50]}...")

                # 2. Проверяем: нужно ли резать картинку?
                # Режем только если has_visual = true И координаты не нулевые
                if t.get('has_visual') is True and t.get('box_2d') != [0,0,0,0]:
                    y0, x0, y1, x1 = [c * h / 1000 if i%2==0 else c * w / 1000 for i, c in enumerate(t['box_2d'])]
                    task_part = main_img.crop((x0, y0, x1, y1))
                    
                    # Логика склейки (если она была нужна)
                    if t.get('needs_stitch') and p2 and 'stitch_box' in t:
                        with Image.open(img2_path) as side_img:
                            sw, sh = side_img.size
                            sy0, sx0, sy1, sx1 = [c * sh / 1000 if i%2==0 else c * sw / 1000 for i, c in enumerate(t['stitch_box'])]
                            stitch_part = side_img.crop((sx0, sy0, sx1, sy1))
                            
                            new_img = Image.new('RGB', (max(task_part.width, stitch_part.width), task_part.height + stitch_part.height + 10), (255,255,255))
                            new_img.paste(task_part, (0, 0))
                            new_img.paste(stitch_part, (0, task_part.height + 10))
                            task_part = new_img

                    task_part.save(base_path / f"task_{t['number']}.jpg", quality=95)
                    print(f"🖼️ Картинка сохранена для №{t['number']}")
                else:
                    print(f"✅ Задача №{t['number']} принята как чистый текст")

        # ВАЖНО: Нам нужно где-то сохранить этот текст! 
        # Давай создадим временный JSON файл для этой страницы, чтобы builder.py его потом собрал
        with open(base_path / f"data_page_{p1}.json", "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=4)

    except Exception as e:
        print(f"⚠️ Ошибка на стр {p1}: {e}")

if __name__ == "__main__":
    for config in TASKS_CONFIG:
        for p in config['pages']:
            # Авто-контекст: всегда смотрим следующую страницу на наличие рисунков
            smart_crop_and_stitch(config['topic'], p, p + 1)
