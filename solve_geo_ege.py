import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "questions/geo_ege.json"

def solve_geo_ege():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден! Проверь, залила ли ты geo_ege.json")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    solved = sum(1 for t in tasks if str(t.get("answer", "")).strip())
    print(f"🌍 Начинаем решать ГЕОГРАФИЮ! Всего задач: {total}, уже решено: {solved}")

    for i, task in enumerate(tasks):
        if str(task.get("answer", "")).strip():
            continue

        print(f"🧠 [{i+1}/{total}] Решаю {task['id']}...")

        prompt = f"""Ты — эксперт ЕГЭ по географии. Реши задание.
Текст задания:
\"\"\"
{task.get('task_text', '')}
\"\"\"
ВЕРНИ ТОЛЬКО ОТВЕТ! Без лишних слов и пояснений.
Если ответом является число, пиши только число.
Если ответом является слово (страна, город, субъект), пиши его в ИМЕНИТЕЛЬНОМ ПАДЕЖЕ."""

        try:
            input_data = {"prompt": prompt}
            
            # Если есть карта или таблица — отправляем её нейронке
            img_rel_path = task.get("image", "")
            if img_rel_path and os.path.exists(img_rel_path):
                with open(img_rel_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                input_data["images"] = [f"data:image/jpeg;base64,{img_data}"]
                print(f"   🗺️ Использую карту/таблицу для решения...")

            output = replicate.run("google/gemini-3-flash", input=input_data)
            answer = "".join(output).strip().replace(".", "")
            
            task["answer"] = answer
            print(f"   ✅ Ответ: {answer}")

            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            
            time.sleep(1.2) # Небольшая пауза

        except Exception as e:
            print(f"   ❌ Ошибка на задаче {task['id']}: {e}")
            time.sleep(5)

    print(f"🎉 УРА! География полностью решена!")

if __name__ == "__main__":
    solve_geo_ege()
