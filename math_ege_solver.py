import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "questions/math_ege.json"

def solve_math_ege():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"📐 Начинаем решать ЕГЭ Математику! Задач: {len(tasks)}")

    for task in tasks:
        if task.get("answer", "").strip(): continue

        print(f"🧠 Решаю {task['id']}...")
        
        prompt = f"""Ты — эксперт ЕГЭ по математике (профиль). Реши задание.
Текст: \"\"\"{task.get('task_text', '')}\"\"\"
ВЕРНИ ТОЛЬКО ЧИСЛО (целое или конечную десятичную дробь).
Никаких пояснений, только результат. Используй точку или запятую для дробей."""

        inputs = {"prompt": prompt}
        if task.get("image") and os.path.exists(task["image"]):
            with open(task["image"], "rb") as img_file:
                inputs["images"] = [f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode('utf-8')}"]

        try:
            output = replicate.run("google/gemini-3-flash", input=inputs)
            ans = "".join(output).strip().replace(" ", "").replace("Ответ:", "")
            task["answer"] = ans
            print(f"✅ Ответ: {ans}")
            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            time.sleep(1)
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    solve_math_ege()
