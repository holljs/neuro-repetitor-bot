import json
import os
import time
import base64
import replicate
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "questions/oge_biology.json"

def solve_biology():
    if not os.path.exists(DB_PATH):
        print(f"❌ Файл {DB_PATH} не найден!")
        return

    with open(DB_PATH, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    total = len(tasks)
    solved = sum(1 for t in tasks if t.get("answer", "").strip())
    print(f"🧬 Начинаем решать Биологию! Всего задач: {total}, уже решено: {solved}")

    for i, task in enumerate(tasks):
        # Если ответ уже есть, пропускаем
        if task.get("answer", "").strip():
            continue

        task_id = task.get("id", f"bio_task_{i}")
        
        # Индикация наличия картинки для логов
        has_img = "(с картинкой)" if task.get("has_visual") and task.get("image") else "(только текст)"
        print(f"🧠 Решаю {task_id} {has_img}...")

        # Строгий промпт для ИИ
        prompt = f"""Ты — эксперт ОГЭ по биологии. Реши это задание из Части 1.
Текст задания:
{task.get('task_text', '')}

ВЕРНИ ТОЛЬКО ОТВЕТ! Строго без объяснений, без точек в конце, без слова "Ответ:".
Если ответ — одна цифра, напиши только цифру (например: 3).
Если ответ — последовательность цифр, напиши их слитно без пробелов (например: 3124).
Если ответ — слово или словосочетание, напиши его (например: митохондрия)."""

        inputs = {"prompt": prompt}

        # Прикрепляем картинку, если она есть в задании
        if task.get("has_visual") and task.get("image"):
            img_path = task["image"]
            if os.path.exists(img_path):
                with open(img_path, "rb") as img_file:
                    img_data = base64.b64encode(img_file.read()).decode("utf-8")
                    inputs["images"] = [f"data:image/jpeg;base64,{img_data}"]
            else:
                print(f"  ⚠️ Внимание: картинка {img_path} не найдена, решаю как текст.")

        try:
            output = replicate.run("google/gemini-3-flash", input=inputs)
            answer = "".join(output).strip()
            
            # Очищаем ответ от случайного мусора
            answer = answer.replace(".", "").replace('"', '').replace("Ответ:", "").strip()

            task["answer"] = answer
            print(f"✅ Ответ: {answer}")

            # Сохраняем прогресс сразу же!
            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
                
            # Маленькая пауза, чтобы сервер Replicate нас не заблокировал за спам
            time.sleep(1)

        except Exception as e:
            print(f"❌ Ошибка при решении {task_id}: {e}")
            time.sleep(5) # Если поймали ошибку (например, лимит), ждем чуть дольше

    print(f"\n🎉 УРА! Биология полностью решена! ({total} задач)")

if __name__ == "__main__":
    solve_biology()
