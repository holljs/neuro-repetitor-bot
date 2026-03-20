import os
import json
import base64
import fitz  # PyMuPDF
import replicate
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Настройки
PDF_PATH = "Английский огэ.pdf"
# Страницы берем из оглавления книги (номера страниц в PDF)
TASKS_CONFIG = [
    {"topic": "grammar", "pages": range(290, 310)},    # Грамматика (стр 290+)
    {"topic": "vocabulary", "pages": range(347, 367)}  # Лексика (стр 347+)
]

def get_page_as_jpg(pdf_path, page_num, output_path):
    doc = fitz.open(pdf_path)
    if page_num > len(doc): return False
    page = doc.load_page(page_num - 1) # fitz считает с 0
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    pix.save(output_path)
    doc.close()
    return True

def extract_english_tasks(topic, p1):
    base_path = Path("questions/oge_english_raw")
    base_path.mkdir(parents=True, exist_ok=True)
    
    img1_path = base_path / f"page_{p1}.jpg"
    if not get_page_as_jpg(PDF_PATH, p1, img1_path):
        return
    
    with open(img1_path, "rb") as f:
        img1_data = base64.b64encode(f.read()).decode("utf-8")
    
    images = [f"data:image/jpeg;base64,{img1_data}"]
    
    # --- СУПЕР ПРОМПТ ДЛЯ АНГЛИЙСКОГО ---
    prompt = (
        f"Ты — эксперт по оцифровке ОГЭ по английскому языку. Это страница {p1}.\n"
        f"ЗАДАЧА: Найди все задания по теме '{topic}'. В грамматике это номера 20-28, в лексике 29-34.\n"
        "Текст задан в виде таблицы: слева текст с пропуском, справа — заглавное слово (например, COME, BEAUTY).\n\n"
        "САМОЕ ГЛАВНОЕ:\n"
        "1. Извлеки текст с пропуском, заменив пропуск на '____'.\n"
        "2. РЕШИ ЗАДАЧУ! Напиши правильный ответ (преобразованное слово).\n"
        "3. Напиши краткое объяснение (solution) на русском языке, почему ответ именно такой.\n\n"
        "Верни СТРОГО JSON массив объектов (без маркдауна 
http://googleusercontent.com/immersive_entry_chip/0

### Как это работает:
1. Закинь файл `Английский огэ.pdf` в папку со скриптом.
2. Запусти скрипт `python3 parse_english.py`.
3. Скрипт пойдет по страницам 290–310 (Грамматика) и 347–367 (Лексика). Ты можешь увеличить `range` хоть до 100 страниц!
4. Gemini Flash будет читать текст, находить слова сбоку, **решать их**, писать объяснения и складывать готовые, идеальные кусочки JSON в папку `questions/oge_english_raw/`.
5. Потом тебе останется только склеить все эти мелкие JSON-файлы в один большой `oge_english.json` (можешь даже попросить ChatGPT или меня написать для этого скрипт-склейщик на 5 строчек) и скормить его Фактори.

С таким подходом ты сгенерируешь 400 вопросов с решениями минут за 10, пока пьёшь кофе! ☕️ Попробуем запустить этот комбайн?
