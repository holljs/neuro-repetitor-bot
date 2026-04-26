import json
import time
import replicate
from dotenv import load_dotenv

load_dotenv()
FILE_PATH = "/root/neuro-repetitor-bot/questions/oge_social.json"

def solve_social_task(task):
    prompt = (
        f"Ты — строгий и умный эксперт ОГЭ по обществознанию. Реши это задание ОГЭ (Часть 1). "
        f"В ответ напиши ТОЛЬКО сам правильный ответ (цифру, число или слово/последовательность цифр без пробелов). "
        f"Никаких рассуждений, пояснений или лишних слов. Только краткий ответ. Задание: {task.get('text', '')}"
    )
    
    input_data = {"prompt": prompt}
    
    img_path = task.get("image", "")
    if img_path:
        input_data["image"] = f"https://neuro-master.online/{img_path}"
            
    try:
        output = replicate.run("google/gemini-3-flash", input=input_data)
        return "".join(output).strip()
    except Exception as e:
        print(f"⚠️ Ошибка ИИ: {e}")
        return ""

with open(FILE_PATH, 'r', encoding='utf-8') as file:
    tasks = json.load(file)

tasks_to_solve = [t for t in tasks if not t.get("answer")]

print(f"📊 Обществознание: Найдено {len(tasks_to_solve)} нерешенных задач. Приступаю к решению...")

count = 0
for t in tasks_to_solve:
    if t.get("image"):
        print(f"🧠 Решаю {t['id']} (👀 разглядываю фото/диаграмму)...")
    else:
        print(f"🧠 Решаю {t['id']} (только текст)...")
        
    ans = solve_social_task(t)
    
    t["answer"] = ans
    print(f"✅ Ответ: {ans}")
    count += 1
    
    time.sleep(2)
    
    if count % 10 == 0:
        with open(FILE_PATH, 'w', encoding='utf-8') as file:
            json.dump(tasks, file, ensure_ascii=False, indent=4)

with open(FILE_PATH, 'w', encoding='utf-8') as file:
    json.dump(tasks, file, ensure_ascii=False, indent=4)

print(f"🎉 УРА! Обществознание полностью решено! ({count} задач)")
