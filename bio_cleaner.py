import json

FILE_PATH = "/root/neuro-repetitor-bot/questions/oge_biology.json"

with open(FILE_PATH, 'r', encoding='utf-8') as f:
    tasks = json.load(f)

unique_tasks = {}
for t in tasks:
    tid = t['id']
    # Если такого ID еще нет — добавляем.
    # Если есть, но у нового варианта есть картинка — перезаписываем!
    if tid not in unique_tasks:
        unique_tasks[tid] = t
    elif t.get('image') and not unique_tasks[tid].get('image'):
        unique_tasks[tid] = t

final_tasks = list(unique_tasks.values())

print(f"🗑️ Было задач до чистки: {len(tasks)}")
print(f"✨ Осталось уникальных, чистых задач: {len(final_tasks)}")

with open(FILE_PATH, 'w', encoding='utf-8') as f:
    json.dump(final_tasks, f, ensure_ascii=False, indent=4)
    
print("✅ База идеально вычищена и готова к загрузке в бота!")

