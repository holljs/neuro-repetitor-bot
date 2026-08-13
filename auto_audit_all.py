import json, os, re

files = [
    'CHECK_1_tochnye.json',
    'CHECK_2_OGE_estestvo.json',
    'CHECK_3_OGE_guman.json',
    'CHECK_4_EGE_estestvo.json',
    'CHECK_5_EGE_guman.json'
]

bad_ids = set()

for fname in files:
    if not os.path.exists(fname):
        continue
        
    with open(fname, 'r', encoding='utf-8') as f:
        tasks = json.load(f)
        
    file_bad = 0
    for t in tasks:
        tid = t.get('id', '')
        text = t.get('task_text', '').strip()
        imgs = t.get('all_images', [])
        audios = t.get('all_audios', [])
        
        is_bad = False
        reason = ""
        
        # 1. Нет текста вообще или он слишком короткий
        if len(text) < 10:
            is_bad = True
            reason = "слишком короткий текст"
            
        # 2. Обрыв в ключевых местах
        elif text.endswith('...') or 'укажите решение неравенства .' in text.lower() or 'укажите решение системы неравенств .' in text.lower():
            is_bad = True
            reason = "пропущено неравенство/уравнение"
            
        # 3. Ссылка на рисунок/график, а картинок нет
        elif any(w in text.lower() for w in ['см. рисунок', 'изображён график', 'изображен график', 'на рисунке', 'на графике']) and not imgs:
            is_bad = True
            reason = "нет картинки к заданию"
            
        # 4. Вставка букв/текст изложения без самого текста
        elif 'прочитайте текст' in text.lower() and len(text) < 60 and not imgs:
            is_bad = True
            reason = "нет текста для чтения"
            
        if is_bad:
            bad_ids.add(tid)
            if tid.startswith('fipi_'): bad_ids.add(tid[5:])
            file_bad += 1

    print(f"🔍 {fname}: найдено {file_bad} явных битых задач.")

print(f"\n🎯 Всего автоматом найдено {len(bad_ids)} масок битых ID!")

# Удаляем найденный мусор из всех файлов
def clean_file(fpath):
    if not os.path.exists(fpath): return
    with open(fpath, 'r', encoding='utf-8') as f: data = json.load(f)
    if isinstance(data, list):
        new_data = [t for t in data if isinstance(t, dict) and t.get('id') not in bad_ids]
        removed = len(data) - len(new_data)
        if removed > 0:
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
            print(f"🧹 {os.path.basename(fpath)}: вырезано {removed} задач.")

for fname in files: clean_file(fname)
if os.path.exists('questions'):
    for qf in os.listdir('questions'):
        if qf.endswith('.json'): clean_file(os.path.join('questions', qf))

print("\n✨ Авто-чистка ВСЕХ 5 БАЗ завершена успешно!")
