import json
import os
import re
from pathlib import Path

# --- НАСТРОЙКИ ---
ANSWERS_FILE = 'answers_math.txt'
QUESTIONS_ROOT = Path('questions')
IMAGES_ROOT = QUESTIONS_ROOT / 'images_oge_math'
OUTPUT_FILE = QUESTIONS_ROOT / 'oge_math.json'

def load_all_answers():
    """Загружает все ответы из файла в один словарь."""
    answers = {}
    if os.path.exists(ANSWERS_FILE):
        with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                # Формат topic_XX_номер: ответ
                match = re.search(r'(topic_\d+)_([\wа-яА-Я\)\*]+):\s*(.*)', line)
                if match:
                    key = f"{match.group(1)}_{match.group(2)}"
                    answers[key] = match.group(3).strip()
    return answers

def build_final_database():
    print("🚀 Начинаю финальную сборку базы...")
    answers_dict = load_all_answers()
    final_tasks = []
    
    skipped_no_answer = 0
    skipped_no_image_t1 = 0

    # Проходим по всем папкам тем в images_oge_math
    if not IMAGES_ROOT.exists():
        print(f"❌ Директория {IMAGES_ROOT} не найдена!")
        return

    for topic_dir in sorted(IMAGES_ROOT.iterdir()):
        if not topic_dir.is_dir(): continue
        
        topic_name = topic_dir.name # например, topic_01
        
        # Ищем все файлы данных по страницам в этой папке
        page_files = list(topic_dir.glob("data_page_*.json"))
        
        for p_file in page_files:
            with open(p_file, 'r', encoding='utf-8') as f:
                try:
                    page_tasks = json.load(f)
                except:
                    continue

                for task in page_tasks:
                    # Формируем ID для сопоставления с ответом
                    t_num = str(task.get('number')).strip()
                    task_id = f"{topic_name}_{t_num}"
                    
                    # 1. Проверка ответа
                    ans = answers_dict.get(task_id)
                    if not ans or ans == "---":
                        skipped_no_answer += 1
                        continue
                    
                    # 2. Проверка картинки для темы 1
                    img_path = task.get('image', '')
                    if topic_name == "topic_01" and (not img_path or img_path == ""):
                        skipped_no_image_t1 += 1
                        continue

                    # Если всё прошло успешно, формируем объект задачи
                    clean_task = {
                        "id": task_id,
                        "topic": topic_name,
                        "number": t_num,
                        "task_text": task.get("task_text", ""),
                        "image": img_path,
                        "answer": ans,
                        "has_visual": task.get("has_visual", False)
                    }
                    final_tasks.append(clean_task)

    # Сохраняем результат
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_tasks, f, ensure_ascii=False, indent=4)

    print(f"\n--- ИТОГИ СБОРКИ ---")
    print(f"✅ Успешно собрано задач: {len(final_tasks)}")
    print(f"🗑 Отсеяно (нет ответа): {skipped_no_answer}")
    print(f"🖼 Отсеяно (нет картинки в теме 1): {skipped_no_image_t1}")
    print(f"📂 Файл готов: {OUTPUT_FILE}")

if __name__ == "__main__":
    build_final_database()
