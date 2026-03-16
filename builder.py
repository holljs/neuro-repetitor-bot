import json
import os
import re
from pathlib import Path

# Настройки
ANSWERS_FILE = 'answers_math.txt'
QUESTIONS_ROOT = Path('questions')
OUTPUT_FILE = QUESTIONS_ROOT / 'oge_math.json'

def load_all_answers():
    """Загружает все ответы из файла в один словарь."""
    answers = {}
    if os.path.exists(ANSWERS_FILE):
        with open(ANSWERS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                # Ищем формат topic_XX_YY: ответ
                match = re.search(r'(topic_\d+_\w+)_(\d+):\s*(.*)', line)
                if match:
                    topic_full = match.group(1) # например topic_04_eq
                    task_num = match.group(2)   # например 1
                    ans_val = match.group(3)    # например 0,8
                    answers[f"{topic_full}_{task_num}"] = ans_val.strip()
    return answers

def build_database():
    answers_map = load_all_answers()
    print(f"Загружено эталонных ответов из файла: {len(answers_map)}")
    
    final_tasks = []

    # 1. Ищем все папки внутри questions (topic_01_models, topic_04_eq и т.д.)
    for topic_folder in QUESTIONS_ROOT.iterdir():
        if topic_folder.is_dir() and topic_folder.name.startswith("topic_"):
            topic_name = topic_folder.name
            print(f"📁 Обработка темы: {topic_name}")

            # 2. Ищем JSON файлы внутри папки темы
            for json_file in topic_folder.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # Если это список задач (как делает Factory)
                        if isinstance(data, list):
                            tasks_list = data
                        else:
                            tasks_list = [data]

                        for task in tasks_list:
                            # Получаем номер задачи
                            raw_num = task.get('number')
                            if not raw_num:
                                match = re.search(r'(\d+)', task.get('text', ''))
                                raw_num = match.group(1) if match else None

                            if raw_num:
                                # Ключ для поиска ответа: "topic_04_eq_1"
                                key = f"{topic_name}_{raw_num}"
                                task['answer'] = answers_map.get(key, "---")
                                task['id'] = key # Уникальный ID для сервера
                            else:
                                task['answer'] = "---"
                            
                            # Наполняем поля текста (для совместимости)
                            content = task.get('text') or task.get('task_text', '')
                            task['text'] = content
                            task['task_text'] = content
                            task['topic'] = topic_name # Записываем название темы
                            
                            final_tasks.append(task)
                except Exception as e:
                    print(f"❌ Ошибка в файле {json_file}: {e}")

    # Сохраняем итоговый файл
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_tasks, f, ensure_ascii=False, indent=4)
    
    linked = len([t for t in final_tasks if t['answer'] != "---"])
    print(f"---")
    print(f"✅ Готово! Всего собрано задач: {len(final_tasks)}")
    print(f"🔗 С пришитыми ответами: {linked}")
    print(f"📂 Файл сохранен: {OUTPUT_FILE}")

if __name__ == "__main__":
    build_database()
