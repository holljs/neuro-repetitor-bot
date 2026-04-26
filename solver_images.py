import json
import time
import replicate
from dotenv import load_dotenv

load_dotenv()
FILE_PATH = "/root/neuro-repetitor-bot/questions/oge_geography.json"

def fix_answer(task):
    prompt = f"Реши это задание ОГЭ по географии. В ответ напиши ТОЛЬКО сам правильный ответ (цифру, слово или последовательность без пробелов). Задание: {task.get('text', '')}"
    
    input_data = {"prompt": prompt}
    
    # Если есть картинка, даем ИИ "глаза"
    img_path = task.get("image", "")
    if img_path:
        # Твой сервер умеет раздавать картинки, так что даем ИИ прямую ссылку!
        if not img_path.startswith("http"):
            input_data["image"] = f"https://neuro-master.online/{img_path}"
        else:
            input_data["image"] = img_path
            
    try:
        output = replicate.run("google/gemini-3-flash", input=input_data)
        return "".join(output).strip()
    except Exception as e:
        print(f"⚠️ Ошибка ИИ: {e}")
        return task.get("answer") # оставляем старый ответ, если что-то пошло не так

# Открываем базу
with open(FILE_PATH, 'r', encoding='utf-8') as file:
    tasks = json.load(file)

# Ищем задачи, которые ИИ решал вслепую (есть картинка или ответ длинный/с пробелами)
tasks_to_fix = []
for t in tasks:
    ans = t.get("answer", "")
    has_image = bool(t.get("image"))
    is_broken = len(ans) > 15 or " " in ans
    
    if has_image or is_broken:
        tasks_to_fix.append(t)

print(f"🔍 Найдено {len(tasks_to_fix)} задач, которые нужно перерешать с картинками. Надеваем очки...")

count = 0
for t in tasks_to_fix:
    print(f"🧠 Перерешиваю {t['id']} (даю картинку)...")
    new_ans = fix_answer(t)
    
    # Записываем новый, уже зрячий ответ
    t["answer"] = new_ans
    print(f"✅ Новый ответ: {new_ans}")
    count += 1
    
    time.sleep(2) # Пауза, чтобы не забанили
    
    if count % 10 == 0:
        with open(FILE_PATH, 'w', encoding='utf-8') as file:
            json.dump(tasks, file, ensure_ascii=False, indent=4)

# Финальное сохранение
with open(FILE_PATH, 'w', encoding='utf-8') as file:
    json.dump(tasks, file, ensure_ascii=False, indent=4)

print(f"🎉 Готово! ИИ прозрел и перерешал {count} задач.")
