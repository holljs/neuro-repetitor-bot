import json, os

target_file = "CHECK_1_tochnye.json"

if not os.path.exists(target_file):
    print(f"⚠️ Файл {target_file} не найден!")
    exit()

with open(target_file, "r", encoding="utf-8") as f:
    tasks = json.load(f)

stop_index = -1

# 1. Сначала ищем по точному вхождению ключа A9D8C0 в id
for idx, task in enumerate(tasks):
    tid = str(task.get("id", ""))
    if "A9D8C0" in tid or "a9d8c0" in tid.lower():
        stop_index = idx
        print(f"🎯 Найдена задача по ID {tid} на позиции {idx + 1}")
        break

# 2. Если не нашли по ID, ищем по тексту задачи "координатная прямая"
if stop_index == -1:
    for idx, task in enumerate(tasks):
        text = task.get("task_text", "")
        if "координатная прямая" in text.lower() and "обрублен" in text.lower():
            stop_index = idx
            print(f"🎯 Найдена задача по тексту на позиции {idx + 1}")
            break

# 3. Если всё равно не нашли — берем серединную отсечку (например, 3500 задач)
if stop_index == -1:
    stop_index = min(3500, len(tasks) // 2)
    print(f"⚠️ Точная точка остановки не найдена, сделали отсечку по умолчанию на индексе {stop_index}")

remaining_tasks = tasks[stop_index + 1:]
output_file = "CHECK_1_REMAINING.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(remaining_tasks, f, ensure_ascii=False, indent=2)

mb_size = round(os.path.getsize(output_file) / (1024 * 1024), 2)
print(f"✅ Успешно сформирован остаток!")
print(f"📍 Отсечено проанализированных: {stop_index + 1} задач.")
print(f"📦 В остаток вошло: {len(remaining_tasks)} задач ({mb_size} МБ).")
print(f"📄 Файл сохранен: {output_file}")
