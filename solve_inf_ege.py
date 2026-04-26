import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "questions/inf_ege.json"

def solve_inf_ege():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден!")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    solved = sum(1 for t in tasks if str(t.get("answer", "")).strip())
    print(f"💻 Начинаем решать Информатику! Всего задач: {total}, уже решено: {solved}")

    for i, task in enumerate(tasks):
        if str(task.get("answer", "")).strip():
            continue

        print(f"🧠 [{i+1}/{total}] Решаю {task['id']}...")

        prompt = f"""Ты — эксперт ЕГЭ по информатике. Реши задание.
Текст задания:
\"\"\"
{task.get('task_text', '')}
\"\"\"
ВЕРНИ ТОЛЬКО ОТВЕТ! Никаких слов "Ответ", решений или пояснений.
Если ответ — число, пиши только его.
Если ответ — последовательность букв или цифр, пиши их СЛИТНО, БЕЗ ПРОБЕЛОВ И ЗАПЯТЫХ (например: 134 или АБВГ)."""

        try:
            input_data = {"prompt": prompt}
            
            # Прикрепляем графы/таблицы, если они есть
            img_rel_path = task.get("image", "")
            if img_rel_path and os.path.exists(img_rel_path):
                with open(img_rel_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                input_data["images"] = [f"data:image/jpeg;base64,{img_data}"]
                print(f"   🖼️ Прикреплена картинка/таблица: {img_rel_path}")

            output = replicate.run("google/gemini-3-flash", input=input_data)
            # Чистим ответ от мусора
            answer = "".join(output).strip().replace(" ", "").replace(".", "")
            
            task["answer"] = answer
            print(f"   ✅ Ответ: {answer}")

            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            
            time.sleep(1.5)

        except Exception as e:
            print(f"   ❌ Ошибка на задаче {task['id']}: {e}")
            time.sleep(5)

    print(f"🎉 УРА! Информатика полностью решена!")

if __name__ == "__main__":
    solve_inf_ege()
