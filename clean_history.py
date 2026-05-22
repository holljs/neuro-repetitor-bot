import json

def clean_database():
    print("Начинаю генеральную уборку базы...")
    with open("questions/history_ege.json", "r", encoding="utf-8") as f:
        tasks = json.load(f)

    cleaned_tasks = []
    
    for t in tasks:
        # 1. Нормализуем номер задания
        raw_number = t.get("number") or t.get("task_number") or t.get("номер_задания") or 0
        try:
            num = int(raw_number)
            # Оставляем ТОЛЬКО Часть 1 (с 1 по 12 задание)
            if num < 1 or num > 12:
                continue
        except (ValueError, TypeError):
            continue # Пропускаем мусор

        # 2. Нормализуем текст
        text = t.get("task_text") or t.get("text") or t.get("content") or t.get("текст_задания") or ""
        if not text.strip():
            continue

        # 3. Формируем идеальный объект
        clean_t = {
            "id": t.get("id", f"hist_ege_{len(cleaned_tasks)+1}"),
            "topic": "history_ege",
            "number": num,
            "task_text": text.strip(),
            "answer": "", # СНОСИМ ВЕСЬ МУСОР, ОСТАВЛЯЕМ ПУСТЫМ ДЛЯ РЕШАТЕЛЯ
            "image": t.get("image", ""),
            "has_visual": t.get("has_visual", False),
            "shared_image_from": t.get("shared_image_from", None)
        }

        cleaned_tasks.append(clean_t)

    # Перезаписываем наш файл идеальными данными
    with open("questions/history_ege.json", "w", encoding="utf-8") as f:
        json.dump(cleaned_tasks, f, ensure_ascii=False, indent=4)
        
    print(f"✅ Очистка завершена! Осталось идеальных заданий Части 1: {len(cleaned_tasks)}")

if __name__ == "__main__":
    clean_database()
