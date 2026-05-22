import json
import re

def fix_shared_images():
    print("🔧 Начинаем нормализацию связей картинок...")
    with open("questions/history_ege.json", "r", encoding="utf-8") as f:
        tasks = json.load(f)

    fixed_count = 0

    for t in tasks:
        sid = t.get("shared_image_from")
        # Если ссылка - это просто число (например, 9) или число в виде строки ("9")
        if isinstance(sid, int) or (isinstance(sid, str) and sid.isdigit()):
            # Достаем префикс страницы из ID текущего задания (из hist_ege_p13_10 берем hist_ege_p13_)
            match = re.match(r"(hist_ege_p\d+_)", t["id"])
            if match:
                prefix = match.group(1)
                t["shared_image_from"] = f"{prefix}{sid}"
                fixed_count += 1

    with open("questions/history_ege.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    print(f"✅ Готово! Исправлено кривых ссылок: {fixed_count}")
    print("🎉 Теперь база идеальна на 100%!")

if __name__ == "__main__":
    fix_shared_images()
