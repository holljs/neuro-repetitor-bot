import json

def fix_db():
    db_path = "questions/oge_history.json"
    
    with open(db_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    fixed_count = 0
    for t in tasks:
        ans = t.get("answer", "")
        # Если ответ - это глюк нейросети (содержит слова-ошибки или слишком длинный)
        if "Пожалуйста" in ans or "текст" in ans or "условие" in ans or len(ans) > 30:
            t["answer"] = "" # Стираем мусор!
            fixed_count += 1

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    print(f"✅ База вылечена! Стёрто 'глючных' ответов: {fixed_count}")

if __name__ == "__main__":
    fix_db()
