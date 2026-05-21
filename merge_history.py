import os
import json
from pathlib import Path

def merge_history_json():
    # Папка с сырыми файлами страниц
    raw_dir = Path("questions/hist_ege_raw")
    # Итоговый файл для бота
    output_file = Path("questions/history_ege.json")
    
    all_tasks = []
    
    if not raw_dir.exists():
        print(f"❌ Папка {raw_dir} не найдена!")
        return

    # Находим все файлы data_page_X.json и сортируем их по номеру страницы
    files = list(raw_dir.glob("data_page_*.json"))
    files.sort(key=lambda x: int(x.stem.split('_')[-1]))
    
    print(f"🔍 Найдено файлов для склейки: {len(files)}")
    
    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                if isinstance(tasks, list):
                    all_tasks.extend(tasks)
        except Exception as e:
            print(f"  ⚠️ Ошибка чтения файла {file_path.name}: {e}")
            
    # Сохраняем итоговый массив
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_tasks, f, ensure_ascii=False, indent=4)
        
    print(f"✅ СКЛЕЙКА ЗАВЕРШЕНА!")
    print(f"🧠 Всего собрано заданий по истории: {len(all_tasks)}")
    print(f"📁 Итоговый файл сохранен: {output_file}")

if __name__ == "__main__":
    merge_history_json()
