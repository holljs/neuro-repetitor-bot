import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

# База Математика ЕГЭ
DB_PATH = "questions/math_ege.json"

def solve_math_ege():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден!")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    # Метод .get("answer", "") вернет пустую строку, даже если ключа "answer" вообще нет
    solved = sum(1 for t in tasks if str(t.get("answer", "")).strip())
    print(f"📐 Начинаем решать МАТЕМАТИКУ ЕГЭ! Всего задач: {total}, уже решено: {solved}")

    count_saved = 0
    for i, task in enumerate(tasks):
        if str(task.get("answer", "")).strip():
            continue

        print(f"🧠 [{i+1}/{total}] Решаю {task['id']}...")

        # Промпт специально для Математики ЕГЭ (профиль)
        prompt = f"""Ты — строгий эксперт ЕГЭ по профильной математике (11 класс). Реши задание.
Текст задания:
\"\"\"
{task.get('task_text', '')}
\"\"\"
ВЕРНИ ТОЛЬКО ОТВЕТ! Без слова "Ответ", без шагов решения и пояснений.
Если это тестовая задача (часть 1) — напиши ТОЛЬКО число (целое или десятичную дробь).
Если это задача части 2 (уравнение, неравенство и т.д.) — напиши только финальный математический ответ."""

        try:
            input_data = {"prompt": prompt}

            # Математика часто содержит графики и геометрию
            img_rel_path = task.get("image", "")
            if img_rel_path and os.path.exists(img_rel_path):
                with open(img_rel_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                input_data["images"] = [f"data:image/jpeg;base64,{img_data}"]
                print(f"   📐 Смотрю на график/чертеж...")

            output = replicate.run("google/gemini-3-flash", input=input_data)
            
            # Очищаем ответ от лишних точек и пробелов
            ans = "".join(output).strip().replace("Ответ:", "").replace("ответ:", "").strip()

            # Вот здесь скрипт СОЗДАСТ поле "answer", даже если его не было
            task["answer"] = ans
            print(f"   ✅ Ответ: {ans}")
            count_saved += 1

            # Сохраняем каждые 10 задач
            if count_saved % 10 == 0:
                with open(DB_PATH, "w", encoding="utf-8") as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=4)

            time.sleep(2) 

        except Exception as e:
            print(f"   ❌ Ошибка на задаче {task['id']}: {e}")
            time.sleep(5)

    # Финальное сохранение
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    print(f"🎉 УРА! Математика ЕГЭ полностью решена!")

if __name__ == "__main__":
    solve_math_ege()
