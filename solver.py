import json
import time
import replicate
from dotenv import load_dotenv

# Загружаем ключи доступа (чтобы Replicate работал)
load_dotenv()

FILE_PATH = "/root/neuro-repetitor-bot/questions/oge_geography.json"

def get_ai_answer(task_text):
    prompt = f"Реши это задание ОГЭ по географии. В ответ напиши ТОЛЬКО сам правильный ответ (одну цифру, слово или последовательность цифр без пробелов и точек). Никаких объяснений.\n\nЗадание: {task_text}"
    
    try:
        output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
        # Склеиваем ответ и убираем лишние пробелы по краям
        return "".join(output).strip()
    except Exception as e:
        print(f"⚠️ Ошибка ИИ: {e}")
        return ""

# Открываем базу
with open(FILE_PATH, 'r', encoding='utf-8') as file:
    tasks = json.load(file)

print(f"🔍 Найдено {len(tasks)} задач. Начинаем решать...")

solved_count = 0
for task in tasks:
    # Если ответа нет - просим нейросеть решить
    if task.get("answer") == "":
        print(f"🧠 Решаю задачу {task.get('id')}...")
        
        correct_answer = get_ai_answer(task.get("text", ""))
        
        if correct_answer:
            task["answer"] = correct_answer
            solved_count += 1
            print(f"✅ Ответ: {correct_answer}")
        
        # Обязательная пауза 2 секунды, чтобы API не заблокировало нас за спам
        time.sleep(2)
        
        # Сохраняем файл каждые 10 задач (чтобы ничего не потерять, если интернет моргнет)
        if solved_count % 10 == 0:
            with open(FILE_PATH, 'w', encoding='utf-8') as file:
                json.dump(tasks, file, ensure_ascii=False, indent=4)
                print(f"💾 Промежуточное сохранение... Решено {solved_count}")

# Финальное сохранение в конце
with open(FILE_PATH, 'w', encoding='utf-8') as file:
    json.dump(tasks, file, ensure_ascii=False, indent=4)

print(f"🎉 УРА! Автоматически решено задач: {solved_count}. База обновлена!")
