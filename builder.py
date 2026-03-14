import os
import json
import base64
from pathlib import Path

# Словарь для превращения имен папок в красивые названия для ученика
TOPICS_MAP = {
    "topic_01_models": "§ 1. Практико-ориентированные задания",
    "topic_02_calc": "§ 2. Вычисления (Дроби, Степени, Корни)",
    "topic_03_units": "§ 3. Единицы измерения величин",
    "topic_04_eq_ineq": "§ 4. Уравнения и неравенства",
    "topic_05_line": "§ 5. Координатная прямая",
    "topic_06_charts": "§ 6. Графики и диаграммы",
    "topic_07_functions": "§ 7. Графики функций",
    "topic_08_expr": "§ 8. Алгебраические выражения",
    "topic_09_formulas": "§ 9. Выражение величины из формулы",
    "topic_10_seq": "§ 10. Последовательности (Прогрессии)",
    "topic_11_text": "§ 11. Текстовые задачи",
    "topic_12_hard_text": "§ 12. Текстовые задачи (сложные)",
    "topic_13_prob": "§ 13. Теория вероятностей",
    "topic_geom_01_angles": "Геометрия: § 1. Подсчёт углов",
    "topic_geom_02_areas": "Геометрия: § 2. Площади фигур",
    "topic_geom_03_pract": "Геометрия: § 3. Реальная планиметрия",
    "topic_geom_04_logic": "Геометрия: § 4. Выбор утверждений"
}

def build_db():
    # Путь к папкам с картинками
    base_dir = Path("questions/images_oge_math")
    all_tasks = []

    if not base_dir.exists():
        print("❌ Папка с картинками не найдена!")
        return

    # Проходим по каждой папке темы
    for folder in base_dir.iterdir():
        if folder.is_dir() and folder.name in TOPICS_MAP:
            topic_title = TOPICS_MAP[folder.name]
            print(f"📦 Обработка темы: {topic_title}...")
            
            # Собираем все картинки в этой папке
            for img_path in folder.glob("*.jpg"):
                with open(img_path, "rb") as f:
                    # Конвертируем в Base64 для передачи в ВК
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")
                
                all_tasks.append({
                    "id": f"{folder.name}_{img_path.stem}",
                    "exam_type": "oge_math",
                    "topic": topic_title,
                    "text": "Решите задачу, представленную на изображении.",
                    "image": f"data:image/jpeg;base64,{img_b64}",
                    "answer": "" # Ответы можно будет вписать через админку позже
                })

    # Сохраняем готовый JSON
    output_file = Path("questions/oge_math.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_tasks, f, ensure_ascii=False, indent=4)
    
    print(f"🚀 Сборка завершена! Создано задач: {len(all_tasks)}")
    print(f"📂 Файл сохранен в: {output_file}")

if __name__ == "__main__":
    build_db()
