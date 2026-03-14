import os, json
from pathlib import Path

def build_database():
    base_dir = Path("questions/images_oge_math")
    database = []
    # Загружаем ответы, если есть
    answers = {}
    if os.path.exists("answers_raw.txt"):
        with open("answers_raw.txt", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    answers[k.strip().lower()] = v.strip()

    for topic_path in sorted(base_dir.iterdir()):
        if topic_path.is_dir():
            t_name = topic_path.name
            for img in sorted(topic_path.glob("task_*.jpg")):
                task_id = img.stem.replace("task_", "")
                key = f"{t_name}_{task_id}".lower()
                database.append({
                    "id": key,
                    "topic": t_name,
                    "image": f"https://raw.githubusercontent.com/holljs/neuro-repetitor-bot/main/{img}",
                    "answer": answers.get(key, "")
                })

    with open("questions/oge_math.json", "w", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False) # Убираем indent для веса
    print(f"✅ База готова: {len(database)} задач")

if __name__ == "__main__":
    build_database()
