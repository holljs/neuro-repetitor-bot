import json, os

def load(name):
    path = os.path.join('questions', name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        print('⚠️ Не читается:', path, e); return None

def merge_dedup(out_name, sources):
    seen_ids = set()
    cleaned_tasks = []
    
    for s in sources:
        data = load(s)
        if data is None:
            continue
            
        # Поддерживаем и списки задач, и словари
        task_list = []
        if isinstance(data, list):
            task_list = data
        elif isinstance(data, dict):
            for src_key, items in data.items():
                if isinstance(items, list):
                    task_list.extend(items)
        
        for t in task_list:
            if isinstance(t, dict):
                tid = t.get('id')
                # Если ID есть и мы его ещё не встречали
                if tid and tid not in seen_ids:
                    seen_ids.add(tid)
                    cleaned_tasks.append(t)
                elif not tid:
                    cleaned_tasks.append(t)

    with open(out_name, 'w', encoding='utf-8') as f:
        json.dump(cleaned_tasks, f, ensure_ascii=False, indent=2)
    
    size_mb = round(os.path.getsize(out_name) / (1024 * 1024), 2)
    print(f'✅ {out_name} — {size_mb} МБ | Уникальных задач: {len(cleaned_tasks)}')

# 1️⃣ Точные науки
merge_dedup('CHECK_1_tochnye.json', [
    'oge_math.json', 'oge_russian.json', 'oge_informatics.json',
    'math_ege.json', 'math_base_ege.json', 'ege_russian.json', 'ege_informatics.json', 'inf_ege.json', 'russian_ege.json'
])

# 2️⃣ ОГЭ Естественные
merge_dedup('CHECK_2_OGE_estestvo.json', [
    'oge_physics.json', 'oge_chemistry.json', 'oge_biology.json', 'oge_biology_2026.json', 'biology_part1.json', 'oge_geography.json'
])

# 3️⃣ ОГЭ Гуманитарные
merge_dedup('CHECK_3_OGE_guman.json', [
    'oge_history.json', 'oge_social.json', 'oge_literature.json',
    'oge_english.json', 'oge_german.json', 'oge_french.json', 'oge_spanish.json'
])

# 4️⃣ ЕГЭ Естественные
merge_dedup('CHECK_4_EGE_estestvo.json', [
    'ege_physics.json', 'phys_ege.json',
    'ege_chemistry.json', 'chem_ege.json',
    'ege_biology.json', 'bio_ege.json',
    'ege_geography.json', 'geo_ege.json'
])

# 5️⃣ ЕГЭ Гуманитарные
merge_dedup('CHECK_5_EGE_guman.json', [
    'ege_history.json', 'history_ege.json',
    'ege_social.json', 'social_ege.json',
    'ege_literature.json',
    'ege_english.json', 'ege_french.json', 'ege_german.json', 'ege_spanish.json', 'ege_chinese.json'
])

print('\n🎉 Идеальная дедупликация завершена!')
