import json, os, re, glob

SUSPICIOUS_PATTERNS = [
    # Задание №1 ОГЭ: "Найдите значение выражения" + почти ничего
    (r'^Найдите значение выражения\s*[\d.,\s]+\.?\s*$', 'oge_math'),
    (r'^Найдите значение выражения\s*.{0,5}$', 'oge_math'),  # слишком коротко
    
    # Пустые или почти пустые задания
    (r'^.{0,20}\.?$', 'any'),  # меньше 20 символов
    
    # Только цифры без операций
    (r'^[^\+\-\*\/\(\)\^√=]+$', 'math'),  # нет мат. символов
    
    # Обрезанные: "46 .", "12.", "1/2 ."
    (r'\d+\s*\.\s*$', 'math'),
]

def is_broken(task, subject):
    text = task.get('question', '') or task.get('text', '') or task.get('condition', '')
    if not text:
        return True, 'empty_text'
    
    # Если есть image с формулой — не битое
    if task.get('image_url') or task.get('image'):
        return False, None
    
    text_clean = text.strip()
    
    # Паттерн 1: "Найдите значение выражения" + только число
    if 'Найдите значение выражения' in text_clean:
        after = text_clean.replace('Найдите значение выражения', '').strip().rstrip('.')
        # После фразы должно быть что-то осмысленное (операции, скобки, дроби)
        if len(after) < 3 or re.match(r'^[\d\s,\.]+$', after):
            return True, f'broken_expression: "{text_clean[:80]}"'
    
    # Паттерн 2: слишком короткое задание (< 15 символов)
    if len(text_clean) < 15 and not task.get('image_url'):
        return True, f'too_short: "{text_clean}"'
    
    # Паттерн 3: обрезанные формулы
    if re.search(r'\d+\s*\.\s*$', text_clean) and 'Найдите' in text_clean:
        return True, f'truncated: "{text_clean[:80]}"'
    
    # Паттерн 4: нет ни одного математического символа в мат. задании
    if subject in ['math', 'oge_math', 'ege_math'] and 'значение выражения' in text_clean.lower():
        if not re.search(r'[+\-*/^=()]|\\frac|\\sqrt|\d+\s*/\s*\d+', text_clean):
            return True, f'no_math_symbols: "{text_clean[:80]}"'
    
    return False, None

# Ищем все JSON-файлы в questions/
json_files = glob.glob('questions/*.json')
total_broken = 0
broken_by_file = {}
broken_examples = []

for fpath in json_files:
    fname = os.path.basename(fpath)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"⚠️ Не удалось прочитать {fname}: {e}")
        continue
    
    broken = []
    for i, task in enumerate(tasks):
        is_br, reason = is_broken(task, fname)
        if is_br:
            broken.append((i, task.get('id', '?'), reason))
    
    if broken:
        broken_by_file[fname] = broken
        total_broken += len(broken)
        broken_examples.extend([(fname, *b) for b in broken[:3]])

# Отчёт
print("\n" + "="*60)
print("🔍 АУДИТ БИТЫХ ЗАДАНИЙ")
print("="*60)
print(f"Проверено файлов: {len(json_files)}")
print(f"Найдено подозрительных заданий: {total_broken}")
print()

for fname, broken in sorted(broken_by_file.items(), key=lambda x: -len(x[1])):
    print(f"📄 {fname}: {len(broken)} битых")
    for idx, tid, reason in broken[:5]:
        print(f"   #{idx+1} [{tid}] {reason}")
    if len(broken) > 5:
        print(f"   ... и ещё {len(broken) - 5}")
    print()

print("="*60)
if total_broken == 0:
    print("✅ Битых заданий не найдено!")
else:
    print(f"⚠️ Найдено {total_broken} подозрительных заданий")
    print("Хочешь удалить их? Запусти: python3 remove_broken_tasks.py")

# Сохраняем список ID на удаление
with open('broken_tasks_to_remove.json', 'w', encoding='utf-8') as f:
    to_save = {fname: [tid for _, tid, _ in broken] for fname, broken in broken_by_file.items()}
    json.dump(to_save, f, ensure_ascii=False, indent=2)
print(f"\n💾 Список ID сохранён: broken_tasks_to_remove.json")
