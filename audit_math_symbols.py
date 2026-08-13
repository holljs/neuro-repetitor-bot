import json, os, re

files = [
    'CHECK_1_tochnye.json',
    'CHECK_2_OGE_estestvo.json',
    'CHECK_4_EGE_estestvo.json'
]

# Паттерны поиска пропущенных знаков (две цифры через пробел вроде "1 3", "15 50" в коротких фрагментах)
bad_symbol_ids = set()

for fname in files:
    if not os.path.exists(fname): continue
    with open(fname, 'r', encoding='utf-8') as f: tasks = json.load(f)
    
    found = 0
    for t in tasks:
        text = t.get('task_text', '')
        tid = t.get('id', '')
        
        # Ищем подозрительные склейки: "1 3", "2 7" в контексте "составляет 1 3" или "равен 1 3"
        if re.search(r'\b\d{1,2}\s+\d{1,2}\b', text) and any(w in text.lower() for w in ['равен', 'равна', 'выражения', 'значение']):
            # Исключаем нормальные варианты вроде "20 колец", "10 машин"
            if not re.search(r'\d+\s+(колец|рублей|машин|пазлов|градусов|чашек|билетов|деталей|мест|ручек|минут|кг|м|см)', text.lower()):
                bad_symbol_ids.add(tid)
                if tid.startswith('fipi_'): bad_symbol_ids.add(tid[5:])
                found += 1

    print(f"📐 {fname}: найдено {found} подозрительных математических выражений без знаков.")

print(f"\n🎯 Итого к удалению: {len(bad_symbol_ids)} масок ID.")

# Очищаем
def clean_file(fpath):
    if not os.path.exists(fpath): return
    with open(fpath, 'r', encoding='utf-8') as f: data = json.load(f)
    if isinstance(data, list):
        new_data = [t for t in data if isinstance(t, dict) and t.get('id') not in bad_symbol_ids]
        removed = len(data) - len(new_data)
        if removed > 0:
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
            print(f"🧹 {os.path.basename(fpath)}: вырезано {removed} задач.")

for fname in files: clean_file(fname)
if os.path.exists('questions'):
    for qf in os.listdir('questions'):
        if qf.endswith('.json'): clean_file(os.path.join('questions', qf))

print("\n✨ Дочистка формул завершена!")
