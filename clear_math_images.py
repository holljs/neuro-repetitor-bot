import json

json_path = 'questions/math_ege.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

count = 0
for task in data:
    if 'image' in task and task['image']:
        task['image'] = ""  # Обнуляем путь к картинке
        count += 1

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"✅ Убрано неправильных картинок: {count}")
