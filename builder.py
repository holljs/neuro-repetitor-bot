import json
import os
import re
from pathlib import Path

# --- НАСТРОЙКИ ---
ANSWERS_FILE = 'answers_math.txt'
QUESTIONS_ROOT = Path('questions')
RAW_DATA_FILE = QUESTIONS_ROOT / 'raw_oge_tasks.json' # Файл, который выдает factory.py
OUTPUT_FILE = QUESTIONS_ROOT / 'oge_math.json'

def load_all_answers():
    """Загружает все ответы из файла в один словарь."""
    answers = {}
    if os.path.exists(ANSWERS_FILE):
        with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                # Ищем формат topic_XX_YY: ответ (учитываем буквы в номерах)
                match = re.search(r'(topic_\d+)_([\wа-яА-Я\)\*]+):\s*(.*)', line)
                if match:
                    topic_full = match.group(1)
                    task_num = match.group(2)
                    ans_val = match.group(3).strip()
                    # Чистим ответ от лишних символов, если они есть
                    answers[f"{topic_full}_{task_num}"] = ans_val
    return answers

def build_database():
    print("🚀 Начинаю сборку чистой базы данных...")
    
    # 1. Загружаем ответы
    answers_dict = load_all_answers()
    print(f"📖 Загружено ответов из файла: {len(answers_dict)}")

    # 2. Загружаем сырые данные из парсера
    if not RAW_DATA_FILE.exists():
        print(f"❌ Ошибка: Файл {RAW_DATA_FILE} не найден. Сначала запусти factory.py!")
        return

    with open(RAW_DATA_FILE, 'r', encoding='utf-8') as f:
        raw_tasks = json.load(f)

    clean_data = []
    skipped_no_answer = 0
    skipped_no_image = 0

    # 3. Фильтруем и чистим
    for task in raw_tasks:
        task_id = task.get("id")
        correct_answer = answers_dict.get(task_id)

        # УСЛОВИЕ 1: Проверка ответа
        if not correct_answer or correct_answer == "---" or correct_answer == "":
            skipped_no_answer += 1
            continue

        # УСЛОВИЕ 2: Проверка картинки для темы 1
        is_topic_1 = "topic_01" in task.get("topic", "")
        img_path = task.get("image", "")
        
        if is_topic_1 and (not img_path or img_path == ""):
            # Попытка найти по номеру страницы, если парсер не привязал
            page_num = task.get("page")
            potential_img = f"questions/images_oge_math/topic_01/task_{task.get('number')}.jpg"
            if os.path.exists(potential_img):
                task["image"] = potential_img
            else:
                skipped_no_image += 1
                continue 

        # Если всё ок, добавляем ответ и сохраняем
        task["answer"] = correct_answer
        clean_data.append(task)

    # 4. Сохраняем финальный результат
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=4)

    print(f"---")
    print(f"✅ Сборка завершена!")
    print(f"📦 Всего задач в базе: {len(clean_data)}")
    print(f"🗑 Пропущено (нет ответа): {skipped_no_answer}")
    print(f"🖼 Пропущено (нет картинки в Topic 1): {skipped_no_image}")
    print(f"📂 Файл сохранен: {OUTPUT_FILE}")

if __name__ == "__main__":
    build_database()
