import os
import json
import base64
import time
import fitz  # PyMuPDF
import replicate
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- НАСТРОЙКИ ---
PDF_PATH = "ЕГЭ 2026 история 11 класс 30 вариантов Артасов.pdf"

START_PAGES = [
    5, 14, 24, 34, 43, 53, 61, 71, 80, 89, 99, 109, 118, 127, 136, 
    145, 155, 164, 173, 183, 193, 202, 211, 220, 230, 240, 249, 259, 268, 277
]
ANSWERS_START = 286

def generate_target_pages():
    pages = []
    for i in range(len(START_PAGES)):
        start = START_PAGES[i]
        end = START_PAGES[i+1] if i + 1 < len(START_PAGES) else ANSWERS_START
        for page_num in range(start, end):
            pages.append(page_num)
    return pages

def smart_crop_history():
    raw_dir = Path("questions/hist_ege_raw")
    img_dir = Path("questions/images_ege_hist")
    
    raw_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(PDF_PATH)
    except Exception as e:
        print(f"❌ Ошибка открытия PDF: {e}")
        return

    target_pages = generate_target_pages()
    print(f"🎯 Начинаем парсинг. Страниц: {len(target_pages)}")

    for page_num in target_pages:
        json_file_path = raw_dir / f"data_page_{page_num}.json"
        
        # СУПЕР-ФИЧА 1: ПРОПУСКАЕМ ТО, ЧТО УЖЕ ГОТОВО
        if json_file_path.exists():
            print(f"⏩ Страница {page_num} уже готова, летим дальше...")
            continue

        pdf_index = page_num - 1
        if pdf_index >= len(doc): continue

        print(f"\n🧠 Анализирую страницу {page_num}...")

        # 1. Рендерим страницу
        page = doc.load_page(pdf_index)
        img_path = raw_dir / f"page_{page_num}.jpg"
        pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        pix.save(img_path)

        # 2. УЖИМАЕМ (только для ИИ)
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            img.thumbnail((600, 800))
            img.save(img_path, "JPEG", quality=15, optimize=True)

        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        print(f"  📦 Вес картинки для отправки: {len(img_data) / 1024:.1f} KB")

        image_uri = f"data:image/jpeg;base64,{img_data}"

        prompt = f"""Ты — строгий эксперт ЕГЭ по Истории. Страница {page_num}.
ИЗВЛЕКИ все задания Части 1. Задания Части 2 строго игнорируй.

ПРАВИЛА ДЛЯ КАРТИНОК И БЛОКОВ ВОПРОСОВ:
В ЕГЭ по истории графическое изображение (карта, марка, плакат) часто относится к целому блоку заданий.
1. Для ПЕРВОГО задания из такого блока: установи "has_visual": true и в "box_2d" УКАЖИ ТОЧНЫЕ КООРДИНАТЫ САМОЙ КАРТИНКИ в формате [ymin, xmin, ymax, xmax] (от 0 до 1000). Не захватывай текст!
2. Для ОСТАЛЬНЫХ заданий из этого же блока: установи "has_visual": false, "box_2d": [0,0,0,0], но обязательно укажи "shared_image_from": <номер первого задания блока>.
3. Если задание вообще не требует картинки, пиши "shared_image_from": null.

ВЕРНИ СТРОГО JSON МАССИВ В ФОРМАТЕ:
[
  {{
    "id": "hist_ege_p{page_num}_{{task_number}}",
    "topic": "history_ege",
    "number": 9,
    "task_text": "Текст вопроса...",
    "answer": "",
    "has_visual": true,
    "box_2d": [100, 100, 400, 900],
    "shared_image_from": null
  }}
]"""

        success = False
        # ДЕЛАЕМ 3 ПОПЫТКИ ОТПРАВКИ
        for attempt in range(3):
            try:
                print(f"  🚀 Отправляем запрос к ИИ (попытка {attempt+1}/3)...")
                output = replicate.run("google/gemini-3-flash", input={"image": image_uri, "prompt": prompt})
                clean_text = "".join(output).replace("```json", "").replace("```", "").strip()
                success = True
                break # Успешно! Выходим из цикла попыток
            except Exception as e:
                print(f"  ⚠️ ОШИБКА: {type(e).__name__} - {e}")
                time.sleep(2)
        
        if not success:
            print(f"❌ Страница {page_num} пропущена из-за постоянных ошибок API.")
            continue

        start_idx = clean_text.find('[')
        end_idx = clean_text.rfind(']') + 1
        
        tasks = []
        if start_idx != -1:
            # СУПЕР-ФИЧА 2: БРОНЯ ОТ КРИВОГО JSON
            try:
                tasks = json.loads(clean_text[start_idx:end_idx])
            except json.JSONDecodeError as e:
                print(f"  ❌ Нейросеть выдала кривой JSON на стр {page_num}. Ошибка: {e}. Пропускаем!")
                continue

        if tasks:
            image_links = {}
            
            # РЕНДЕРИМ В HD-КАЧЕСТВЕ ДЛЯ ВЫРЕЗАНИЯ КРАСИВЫХ КАРТИНОК
            pix_high = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            high_res_path = raw_dir / f"high_page_{page_num}.jpg"
            pix_high.save(high_res_path)

            with Image.open(high_res_path) as main_img:
                w, h = main_img.size
                for t in tasks:
                    task_number = t.get('number', 'X')
                    
                    if t.get('has_visual') and 'box_2d' in t and len(t['box_2d']) == 4 and t['box_2d'] != [0,0,0,0]:
                        img_filename = f"task_p{page_num}_{task_number}.jpg"
                        save_path = img_dir / img_filename
                        
                        coords = t['box_2d']
                        y0, x0, y1, x1 = [coords[0]*h/1000, coords[1]*w/1000, coords[2]*h/1000, coords[3]*w/1000]
                        
                        task_img = main_img.crop((max(0, x0-10), max(0, y0-10), min(w, x1+10), min(h, y1+10)))
                        task_img.save(save_path, quality=95)

                        saved_image_path = f"questions/images_ege_hist/{img_filename}"
                        t['image'] = saved_image_path
                        image_links[task_number] = saved_image_path
                        print(f"  🖼️ Вырезана HD-картинка для №{task_number}")
                        
                    elif t.get('shared_image_from') is not None:
                        parent_number = t['shared_image_from']
                        if parent_number in image_links:
                            t['image'] = image_links[parent_number]
                            print(f"  🔗 Привязана общая картинка от №{parent_number} к №{task_number}")
                        else:
                            t['image'] = ""
                    else:
                        t['image'] = ""

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
        
        print(f"✅ Страница {page_num} обработана успешно.")

    doc.close()
    print("\n🏁 ПАРСИНГ ЕГЭ ИСТОРИИ ЗАВЕРШЕН!")

if __name__ == "__main__":
    smart_crop_history()
