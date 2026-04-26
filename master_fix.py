import json
import os

GLOBAL_CORRECTIONS = {
    "questions/phys_ege.json": {
        "phys_ege_p72_10": "23",
        "phys_ege_p114_5": "" 
    },
    "questions/russian_ege.json": {  # ИСПРАВЛЕНО ИМЯ ФАЙЛА
        "rus_ege_p48_8": "36417",
        "rus_ege_p74_8": "",
        "rus_ege_p5_10": "",
        "rus_ege_p74_11": ""
    },
    "questions/oge_chemistry.json": {
        "chem_oge_p105_19": "127,7",
        "chem_oge_p167_14": "",
        "chem_oge_p148_19": "679,2"
    },
    "questions/oge_physics.json": {
        "phys_oge_p94_14": "23",
        "phys_oge_p129_11": ""
    },
    "questions/oge_russian.json": {
        "rus_oge_p190_6": "14",
        "rus_oge_p72_5": "23568"
    },
    "questions/oge_social.json": {
        "soc_oge_v10_19": "",
        "soc_oge_v19_19": "",
        "soc_oge_v2_20": "Педагог"
    },
    "questions/oge_history.json": {
        "hist_oge_p14_9": "",
        "hist_oge_p30_8": "",
        "hist_oge_p56_16": "2",
        "hist_oge_p56_17": "3",
        "hist_oge_p126_17": "2",
        "hist_oge_p157_17": "1",
        "hist_oge_p164_14": "",
        "hist_oge_p173_17": "2",
        "hist_oge_p195_9": ""
    },
    "questions/oge_geography.json": {
        "geo_oge_p8_20": "31",
        "geo_oge_p8_21": "Нигерия",
        "geo_oge_p8_22": "13",
        "geo_oge_p17_20": "24",
        "geo_oge_p17_21": "Хабаровскийкрай",
        "geo_oge_p17_22": "45",
        "geo_oge_p36_23": "",
        "geo_oge_p165_5": "",
        "geo_oge_p165_6": ""
    },
    "questions/oge_biology.json": {
        "bio_oge_p29_7": "",
        "bio_oge_p268_19": "146" 
    },
    "questions/ege_english.json": {  # ИСПРАВЛЕНО ИМЯ ФАЙЛА
        "eng_ege_p120_28": ""
    },
    "questions/ege_literature.json": {  # ИСПРАВЛЕНО ИМЯ ФАЙЛА
        "lit_ege_p61_1": "КИРСАНОВ",
        "lit_ege_p20_2": "",
        "lit_ege_p37_8": "123567"
    }
}

def apply_global_patch():
    total_fixes = 0
    print("🌍 Запускаю глобальный аудит и патч баз данных...")

    for file_path, corrections in GLOBAL_CORRECTIONS.items():
        if not os.path.exists(file_path):
            print(f"⚠️ Файл {file_path} не найден! Проверь папку questions.")
            continue
        
        with open(file_path, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        file_fixes_count = 0
        
        for task in tasks:
            task_id = task.get("id")
            if task_id in corrections:
                old_answer = task.get("answer", "")
                new_answer = corrections[task_id]
                task["answer"] = new_answer
                print(f"   🔧 {task_id}: '{old_answer}' -> '{new_answer}'")
                file_fixes_count += 1

        if file_fixes_count > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=4)
            print(f"✅ В файле {file_path} исправлено {file_fixes_count} задач.\n")
            total_fixes += file_fixes_count

    print(f"🎉 Глобальный патч завершен! Успешно внесено изменений: {total_fixes}")

if __name__ == "__main__":
    apply_global_patch()
