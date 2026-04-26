import json
import os

# Файлы, в которых ДипСик нашел составные ответы
FILES_TO_PROCESS = [
    "questions/oge_geography.json",
    "questions/oge_history.json"
]

def split_compound_answers():
    total_fixed = 0
    print("✂️ Запускаю скрипт разделения составных ответов...")

    for file_path in FILES_TO_PROCESS:
        if not os.path.exists(file_path):
            print(f"⚠️ Файл {file_path} не найден. Пропускаю.")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        file_fixes_count = 0
        
        for task in tasks:
            answer = str(task.get("answer", ""))
            
            # Ищем ответы, в которых есть перенос строки
            if "\n" in answer:
                # Разбиваем ответ на части и убираем лишние пробелы
                parts = [p.strip() for p in answer.split("\n") if p.strip()]
                
                if len(parts) > 1:
                    task_id = task.get("id", "")
                    
                    # Умная нумерация: вытаскиваем номер из конца ID (например "geo_oge_p13_8" -> 8)
                    try:
                        base_num = int(task_id.split("_")[-1])
                    except ValueError:
                        base_num = 1 # Запасной вариант, если ID странный
                    
                    # Создаем новые отдельные поля для ВК-приложения
                    for i, part in enumerate(parts):
                        new_key = f"answer_{base_num + i}"
                        task[new_key] = part
                    
                    # В основном поле answer оставляем только первую часть ответа, 
                    # чтобы не пугать стандартные парсеры
                    task["answer"] = parts[0]
                    
                    print(f"   ✂️ Разрезан {task_id}: созданы поля от {base_num} до {base_num + len(parts) - 1}")
                    file_fixes_count += 1

        if file_fixes_count > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            print(f"✅ В файле {file_path} успешно разделено {file_fixes_count} задач.\n")
            total_fixed += file_fixes_count
        else:
            print(f"   ℹ️ В файле {file_path} составных ответов не найдено.\n")

    print(f"🎉 Разделение завершено! Всего обработано составных задач: {total_fixed}")

if __name__ == "__main__":
    split_compound_answers()
