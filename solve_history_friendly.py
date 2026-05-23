import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "questions/history_ege.json"

def solve_hist_ege():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден!")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    solved = sum(1 for t in tasks if str(t.get("answer", "")).strip())
    print(f"🎓 Начинаем решать ИСТОРИЮ (Для людей)! Всего задач: {total}, уже решено: {solved}")

    image_map = {t["id"]: t.get("image") for t in tasks if t.get("image")}

    for i, task in enumerate(tasks):
        if str(task.get("answer", "")).strip():
            continue

        print(f"🧠 [{i+1}/{total}] Решаю {task['id']}...")

        # НОВЫЙ ДРУЖЕЛЮБНЫЙ ПРОМПТ
        prompt = f"""Ты — заботливый репетитор по Истории. Твоя цель — дать короткий правильный ответ на задание.
Текст задания:
\"\"\"
{task.get('task_text', '')}
\"\"\"
ПРАВИЛА ОТВЕТА:
1. ВЕРНИ ТОЛЬКО САМ ОТВЕТ в понятном, читаемом виде для человека (с пробелами и заглавными буквами).
2. Например, пиши "Петр Первый" (а не петрпервый). 
3. Если это дата/год, пиши понятно, например "1941" или "XIX век" или "Девятнадцатый".
4. СТРОГИЙ ЗАПРЕТ: Не пиши никаких пояснений, рассуждений или вводных фраз (никаких "Для решения задания необходимо..."). ТОЛЬКО сам ответ. Точка в конце не нужна."""

        try:
            input_data = {"prompt": prompt}
            
            img_rel_path = task.get("image", "")
            if not img_rel_path and task.get("shared_image_from"):
                parent_id = task.get("shared_image_from")
                img_rel_path = image_map.get(parent_id, "")

            if img_rel_path and os.path.exists(img_rel_path):
                with open(img_rel_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                input_data["image"] = f"data:image/jpeg;base64,{img_data}"
                print(f"    🗺️ Использую историческую карту/иллюстрацию...")

            output = replicate.run("google/gemini-3-flash", input=input_data)
            # Убрали жесткое удаление пробелов, оставили только очистку от кавычек
            answer = "".join(output).strip().replace('"', '').replace("'", "")
            
            # Удаляем точку в самом конце, если ИИ её всё-таки поставил
            if answer.endswith('.'):
                answer = answer[:-1]
            
            task["answer"] = answer
            print(f"    ✅ Ответ: {answer}")

            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            
            time.sleep(1.5)

        except Exception as e:
            print(f"    ❌ Ошибка на задаче {task['id']}: {e}")
            time.sleep(5)

    print(f"🎉 УРА! История полностью решена в человеческом формате!")

if __name__ == "__main__":
    solve_hist_ege()
