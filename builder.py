import json
import os
import re

# Названия файлов
ANSWERS_FILE = 'answers_math.txt'
DATA_DIR = 'questions/images_oge_math/topic_04_eq/'
OUTPUT_FILE = 'questions/oge_math.json'
TOPIC_PREFIX = 'topic_04' # Указываем тему явно

def load_answers():
    answers = {}
    if os.path.exists(ANSWERS_FILE):
        with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            # Ищем формат topic_04_1: 0,8 
            pattern = rf'{TOPIC_PREFIX}_(\d+):\s*([^\n\r]+)'
            matches = re.findall(pattern, content)
            for num, val in matches:
                answers[int(num)] = val.strip()
    return answers

def build_database():
    answers_map = load_answers()
    print(f"Загружено ответов из файла: {len(answers_map)}")
    
    final_tasks = []
    
    if not os.path.exists(DATA_DIR):
        print(f"Ошибка: Папка {DATA_DIR} не найдена")
        return

    for filename in os.listdir(DATA_DIR):
        if filename.startswith("data_page_") and filename.endswith(".json"):
            with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
                page_data = json.load(f)
                for task in page_data:
                    # Извлекаем номер из поля "number" или из текста
                    raw_number = task.get('number', '')
                    if not raw_number:
                        num_match = re.search(r'(\d+)', task.get('text', ''))
                        raw_number = num_match.group(1) if num_match else None
                    
                    if raw_number:
                        task_id = int(raw_number)
                        # Пытаемся найти ответ по номеру
                        task['answer'] = answers_map.get(task_id, "---")
                    else:
                        task['answer'] = "---"
                    
                    # Обеспечиваем наличие нужных полей для ВК
                    task['task_text'] = task.get('text', task.get('task_text', ''))
                    final_tasks.append(task)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_tasks, f, ensure_ascii=False, indent=4)
    
    # Считаем, сколько реально ответов проставилось
    linked = len([t for t in final_tasks if t['answer'] != "---"])
    print(f"✅ База собрана! Всего задач: {len(final_tasks)}, с ответами: {linked}")

if __name__ == "__main__":
    build_database()
