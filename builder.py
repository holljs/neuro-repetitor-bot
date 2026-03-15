import os
import json
from pathlib import Path

def build_database():
    all_tasks = []
    base_dir = Path("questions/images_oge_math")
    
    # Проходим по всем папкам тем (например, topic_04_eq)
    for topic_path in base_dir.iterdir():
        if not topic_path.is_dir(): continue
        
        topic_name = topic_path.name
        
        # 1. Сначала ищем все JSON-файлы с данными страниц
        json_files = list(topic_path.glob("data_page_*.json"))
        
        for j_file in json_files:
            with open(j_file, "r", encoding="utf-8") as f:
                page_tasks = json.load(f)
                
            for t in page_tasks:
                task_id = f"{topic_name}_{t['number']}"
                image_filename = f"task_{t['number']}.jpg"
                image_path = topic_path / image_filename
                
                # Формируем объект задачи
                task_data = {
                    "id": task_id,
                    "topic": topic_name,
                    "text": t.get("task_text", ""), # Берем текст из ИИ-оцифровки
                    "answer": t.get("answer", ""),
                    "exam_type": "oge_math"
                }
                
                # Если для этой задачи была сохранена картинка (график)
                if image_path.exists():
                    # Здесь можно оставить ссылку на GitHub или перевести в Base64
                    task_data["image"] = f"https://raw.githubusercontent.com/holljs/neuro-repetitor-bot/main/{image_path}"
                else:
                    task_data["image"] = "" # Картинки нет, будет только текст
                
                all_tasks.append(task_data)

    # Сохраняем итоговую базу
    with open("questions/oge_math.json", "w", encoding="utf-8") as f:
        json.dump(all_tasks, f, ensure_ascii=False, indent=4)
    
    print(f"✅ База собрана: {len(all_tasks)} задач.")

if __name__ == "__main__":
    build_database()
