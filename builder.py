import os
import json
import re
from pathlib import Path

def get_answer_for_task(topic, task_id):
    """Ищет ответ в answers_raw.txt с учетом темы"""
    search_key = f"{topic}_{task_id}".lower()
    try:
        if not os.path.exists("answers_raw.txt"):
            return ""
            
        with open("answers_raw.txt", "r", encoding="utf-8") as f:
            for line in f:
                # Ищем строку вида "topic_01_1а: 5786"
                if line.lower().startswith(search_key):
                    return line.split(":", 1)[1].strip()
    except Exception:
        return ""
    return ""

def build_database():
    base_dir = Path("questions/images_oge_math")
    database = []

    for topic_path in sorted(base_dir.iterdir()):
        if topic_path.is_dir():
            topic_name = topic_path.name
            print(f"📦 Собираю тему: {topic_name}")
            
            for img_path in sorted(topic_path.glob("task_*.jpg")):
                task_id = img_path.stem.replace("task_", "")
                answer = get_answer_for_task(topic_name, task_id)
                
                database.append({
                    "id": f"{topic_name}_{task_id}",
                    "topic": topic_name,
                    "image": str(img_path),
                    "answer": answer
                })

    with open("oge_math.json", "w", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False, indent=4)
    
    found = len([i for i in database if i['answer']])
    print(f"🚀 Готово! Задач: {len(database)}, Ответов найдено: {found}")

if __name__ == "__main__":
    build_database()
