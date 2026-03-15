import json
import os
import re

# Пути
ANSWERS_FILE = 'ответы математика огэ.txt'
DATA_DIR = 'questions/images_oge_math/topic_04_eq/'
OUTPUT_FILE = 'questions/oge_math.json'

def load_answers():
    answers = {}
    if os.path.exists(ANSWERS_FILE):
        with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            # Ищем строки вида topic_04_18: 25
            matches = re.findall(r'topic_04_(\d+):\s*([^\n\r]+)', content)
            for num, val in matches:
                answers[int(num)] = val.strip()
    return answers

def build_database():
    answers_map = load_answers()
    final_tasks = []
    
    # Собираем все файлы data_page_*.json
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("data_page_") and filename.endswith(".json"):
            with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
                page_data = json.load(f)
                
                for task in page_data:
                    # Извлекаем номер задачи из текста (например, "18. x - 19...")
                    num_match = re.search(r'^(\d+)', task.get('text', ''))
                    if num_match:
                        task_id = int(num_match.group(1))
                        # Если нашли ответ в файле ответов - вставляем его!
                        if task_id in answers_map:
                            task['answer'] = answers_map[task_id]
                    
                    final_tasks.append(task)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_tasks, f, ensure_ascii=False, indent=4)
    
    print(f"✅ База собрана и ответы пришиты! Всего задач: {len(final_tasks)}")

if __name__ == "__main__":
    build_database()
