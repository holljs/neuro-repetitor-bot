import json
import os

# Черный список: Файл -> список ID задач-инвалидов
TASKS_TO_DELETE = {
    "questions/oge_informatics.json": [
        "inf_oge_p24_2", 
        "inf_oge_p25_2", 
        "inf_oge_p35_2",
        "inf_oge_p147_6", 
        "inf_oge_p157_6", 
        "inf_oge_p187_6", 
        "inf_oge_p197_6"
    ],
    "questions/oge_biology.json": [
        "bio_oge_p275_10"
    ]
}

def delete_bad_tasks():
    total_deleted = 0
    print("🗑️ Запускаю зачистку битых задач...")

    for file_path, bad_ids in TASKS_TO_DELETE.items():
        if not os.path.exists(file_path):
            print(f"⚠️ Файл {file_path} не найден. Пропускаю.")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        original_count = len(tasks)
        
        # Оставляем только те задачи, ID которых НЕТ в черном списке
        good_tasks = [task for task in tasks if task.get("id") not in bad_ids]
        deleted_count = original_count - len(good_tasks)

        if deleted_count > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(good_tasks, f, ensure_ascii=False, indent=4)
            print(f"   ✅ Из файла {file_path} безвозвратно удалено задач: {deleted_count}")
            total_deleted += deleted_count
        else:
            print(f"   ℹ️ В файле {file_path} указанные задачи не найдены (уже удалены?).")

    print(f"🎉 Зачистка завершена! Всего удалено задач: {total_deleted}")

if __name__ == "__main__":
    delete_bad_tasks()
