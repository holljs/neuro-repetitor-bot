import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "questions/oge_history.json"

def solve_history():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден!")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    solved = sum(1 for t in tasks if t.get("answer", "").strip())
    print(f"🏛 Начинаем решать Историю! Всего задач: {total}, уже решено: {solved}")

    for i, task in enumerate(tasks):
        if task.get("answer", "").strip():
            continue

        task_id = task.get("id", f"hist_task_{i}")
        has_img = "(с картинкой)" if task.get("has_visual") and task.get("image") else "(только текст)"
        
        # ДЕБАГ: выводим кусочек текста в консоль, чтобы убедиться, что он есть!
        text_preview = task.get("task_text", "").replace('\n', ' ')[:40]
        print(f"🧠 Решаю {task_id} {has_img}. Текст: {text_preview}...")

        # БРОНЕБОЙНЫЙ ПРОМПТ
        prompt = f"""Ты — строгий эксперт ОГЭ по истории. Реши задание, текст которого указан ниже в тройных кавычках.

\"\"\"
{task.get('task_text', 'ТЕКСТ ОТСУТСТВУЕТ')}
\"\"\"

ВЕРНИ ТОЛЬКО ОТВЕТ! Строго без объяснений, без точек в конце, без слова "Ответ:".
Если ответ — одна цифра, напиши только цифру (например: 3).
Если ответ — последовательность цифр, напиши их слитно без пробелов (например: 3124).
Если ответ — слово или имя, напиши его (например: Александр)."""

        inputs = {"prompt": prompt}

        if task.get("has_visual") and task.get("image"):
            img_path = task["image"]
            if os.path.exists(img_path):
                with open(img_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                    inputs["images"] = [f"data:image/jpeg;base64,{img_data}"]
            else:
                print(f"  ⚠️ Внимание: картинка {img_path} не найдена.")

        try:
            output = replicate.run("google/gemini-3-flash", input=inputs)
            answer = "".join(output).strip()
            
            answer = answer.replace(".", "").replace('"', '').replace("Ответ:", "").strip()

            task["answer"] = answer
            print(f"✅ Ответ: {answer}")

            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
                
            time.sleep(1.5)

        except Exception as e:
            print(f"❌ Ошибка при решении {task_id}: {e}")
            time.sleep(5)

    print(f"\n🎉 УРА! История полностью решена! ({total} задач)")

if __name__ == "__main__":
    solve_history()
