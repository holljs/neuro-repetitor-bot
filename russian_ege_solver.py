import json
import os
import time
import replicate
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "questions/russian_ege.json"

def solve_russian_ege():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден!")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    solved = sum(1 for t in tasks if t.get("answer", "").strip())
    print(f"🇷🇺 Начинаем решать Русский язык! Всего задач: {total}, уже решено: {solved}")

    for i, task in enumerate(tasks):
        if task.get("answer", "").strip():
            continue

        print(f"🧠 [{i+1}/{total}] Решаю {task['id']}...")

        prompt = f"""Ты — эксперт ЕГЭ по русскому языку. Реши задание.
Текст задания:
\"\"\"
{task.get('task_text', '')}
\"\"\"
ВЕРНИ ТОЛЬКО ОТВЕТ! Без слова "Ответ", без пояснений. 
Если ответом является слово, пиши его БЕЗ ТОЧКИ в конце.
Если ответом является последовательность цифр, пиши их БЕЗ ПРОБЕЛОВ и запятых."""

        try:
            output = replicate.run("google/gemini-3-flash", input={"prompt": prompt})
            answer = "".join(output).strip().replace(" ", "").replace(".", "")
            
            task["answer"] = answer
            print(f"✅ Ответ: {answer}")

            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            
            time.sleep(1.2) # Небольшая пауза, чтобы API не ругалось

        except Exception as e:
            print(f"❌ Ошибка на задаче {task['id']}: {e}")
            time.sleep(5)

    print(f"🎉 УРА! Русский язык полностью решен!")

if __name__ == "__main__":
    solve_russian_ege()
