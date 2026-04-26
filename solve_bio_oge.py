import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

# База биологии ОГЭ
DB_PATH = "questions/oge_biology.json"

def solve_bio_oge():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден!")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    solved = sum(1 for t in tasks if str(t.get("answer", "")).strip())
    print(f"🧬 Начинаем решать БИОЛОГИЮ ОГЭ! Всего задач: {total}, уже решено: {solved}")

    count_saved = 0
    for i, task in enumerate(tasks):
        if str(task.get("answer", "")).strip():
            continue

        print(f"🧠 [{i+1}/{total}] Решаю {task['id']}...")

        # Промпт для ОГЭ по биологии
        prompt = f"""Ты — строгий эксперт ОГЭ по биологии (9 класс). Реши задание.
Текст задания:
\"\"\"
{task.get('task_text', task.get('text', ''))}
\"\"\"
ВЕРНИ ТОЛЬКО ОТВЕТ! Без лишних слов, без слова "Ответ", без пояснений.
Если ответом является последовательность цифр, пиши только цифры БЕЗ ПРОБЕЛОВ.
Если ответом является слово, пиши его в ИМЕНИТЕЛЬНОМ ПАДЕЖЕ, БЕЗ ТОЧКИ в конце."""

        try:
            input_data = {"prompt": prompt}

            # Работа с картинками (в биологии их очень много)
            img_rel_path = task.get("image", "")
            if img_rel_path and os.path.exists(img_rel_path):
                with open(img_rel_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                input_data["images"] = [f"data:image/jpeg;base64,{img_data}"]
                print(f"   🦠 Изучаю схему/рисунок...")

            output = replicate.run("google/gemini-3-flash", input=input_data)
            
            # Очистка ответа
            ans = "".join(output).strip().replace(".", "")
            if ans.replace(" ", "").isdigit():
                ans = ans.replace(" ", "")

            task["answer"] = ans
            print(f"   ✅ Ответ: {ans}")
            count_saved += 1

            # Сохраняем каждые 10 задач, чтобы ничего не потерять
            if count_saved % 10 == 0:
                with open(DB_PATH, "w", encoding="utf-8") as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=4)

            time.sleep(2) # Пауза, чтобы не забанил сервер

        except Exception as e:
            print(f"   ❌ Ошибка на задаче {task['id']}: {e}")
            time.sleep(5)

    # Финальное сохранение
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    print(f"🎉 УРА! Биология ОГЭ полностью решена!")

if __name__ == "__main__":
    solve_bio_oge()
