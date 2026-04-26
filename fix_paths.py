import json
import os

# Путь к твоему JSON
json_path = 'questions/math_ege.json'
# Путь к реальным картинкам
img_dir = 'questions/images_ege_math_profile'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Составляем список всех реальных картинок в папке
real_images = os.listdir(img_dir)

fixed_count = 0
for task in data:
    if 'image' in task and task['image']:
        # Пытаемся сопоставить задачу и картинку
        # Обычно в парсерах номер задачи и номер страницы совпадают
        task_num = task.get('number', '')
        # Ищем файл, который начинается на task_{номер}_
        match = [img for img in real_images if img.startswith(f"task_{task_num}_")]
        
        if match:
            # Обновляем путь на тот, что реально существует
            task['image'] = f"questions/images_ege_math_profile/{match[0]}"
            fixed_count += 1

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"✅ Готово! Исправлено путей: {fixed_count}")
