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
    print(f"⚔️ Начинаем решать ИСТОРИЮ! Всего задач: {total}, уже решено: {solved}")

    # Создаем словарь для быстрого поиска картинок по ID родительского задания
    image_map = {t["id"]: t.get("image") for t in tasks if t.get("image")}

    for i, task in enumerate(tasks):
        if str(task.get("answer", "")).strip():
            continue

        print(f"🧠 [{i+1}/{total}] Решаю {task['id']}...")

        prompt = f"""Ты — строгий эксперт и председатель комиссии ЕГЭ по Истории. Реши задание Части 1.
Текст задания:
\"\"\"
{task.get('task_text', '')}
\"\"\"
ВЕРНИ СТРОГО КРАТКИЙ ОТВЕТ, который примет автоматическая система проверки! Без лишних слов, пояснений, точек и кавычек.
- Если ответом является имя правителя, пиши его слитно (например: ивангрозный или петрпервый).
- Если ответом является год или век словом, пиши слово (например: одиннадцатый).
- Если требуется последовательность цифр, пиши только цифры без пробелов и запятых."""

        try:
            input_data = {"prompt": prompt}
            
            # Ищем картинку: либо своя собственная, либо берем у родителя через shared_image_from
            img_rel_path = task.get("image", "")
            if not img_rel_path and task.get("shared_image_from"):
                parent_id = task.get("shared_image_from")
                img_rel_path = image_map.get(parent_id, "")

            if img_rel_path and os.path.exists(img_rel_path):
                with open(img_rel_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                input_data["image"] = f"data:image/jpeg;base64,{img_data}"
                print(f"    🗺️ Использую историческую карту/иллюстрацию для решения...")

            output = replicate.run("google/gemini-3-flash", input=input_data)
            answer = "".join(output).strip().replace(".", "").replace('"', '').replace("'", "")
            
            task["answer"] = answer
            print(f"    ✅ Ответ: {answer}")

            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            
            time.sleep(1.5)

        except Exception as e:
            print(f"    ❌ Ошибка на задаче {task['id']}: {e}")
            time.sleep(5)

    print(f"🎉 УРА! История полностью решена!")

if __name__ == "__main__":
    solve_hist_ege()
