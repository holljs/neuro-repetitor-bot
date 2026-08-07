import json, re, os, glob

# 🗑 Ключевые слова для УДАЛЕНИЯ задания
JUNK_MARKERS = [
    r'инструкци[яи]\s+по\s+выполнен',
    r'на\s+выполнение\s+заданий\s+.*\s*отводитс',
    r'часть\s+[12]\s+включает',
    r'при\s+выполнении\s+работы\s+не\s+разрешаетс',
    r'при\s+необходимости\s+можно\s+пользоваться\s+черновиком',
    r'советуем\s+выполнять\s+задани',
    r'желаем\s+успеха',
    r'запиши\s+текст\s+под\s+диктовку',
    r'записи\s+в\s+черновике\s+не\s+будут',
    r'таблиц[аы]\s+перевода\s+баллов',
    r'систем[аы]\s+оценивани',
    r'ответы\s+на\s+задани.*запиш',
    r'проверочн.*работ.*по.*[а-я]+\s+отводитс',
]

# 🔍 Задания со ссылками на отсутствующий текст
TEXT_REF_RE = re.compile(
    r'(из\s+\d+-?го\s+предложен|в\s+\d+-?м\s+предложен|'
    r'из\s+текста.*выпиш|выпиши.*из\s+текст|'
    r'по\s+тексту|в\s+тексте\s+\d|'
    r'перечисленн.*в\s+текст|'
    r'каком\s+из\s+предложен)',
    re.I
)

stats = {"files": 0, "deleted": 0, "kept": 0}

for f in sorted(glob.glob('questions/vpr_*.json')):
    tasks = json.load(open(f))
    before = len(tasks)
    clean = []
    for t in tasks:
        txt = t["task_text"]
        low = txt.lower()
        
        # 1) Убираем инструкции/диктанты
        if any(re.search(p, low) for p in JUNK_MARKERS):
            stats["deleted"] += 1
            continue
        
        # 2) Убираем "пустые ссылки" на текст (задание ссылается на текст, но самого текста < 300 символов в задании)
        if TEXT_REF_RE.search(txt):
            # проверяем: есть ли в задании САМ текст (обычно > 300 символов)
            if len(txt) < 300:
                stats["deleted"] += 1
                continue
        
        # 3) Убираем слишком короткие огрызки
        if len(txt.strip()) < 50:
            stats["deleted"] += 1
            continue
        
        clean.append(t)
    
    if len(clean) != before:
        json.dump(clean, open(f, 'w'), ensure_ascii=False, indent=2)
        stats["files"] += 1
        stats["kept"] += len(clean)

print(f"✅ Обработано файлов: {stats['files']}")
print(f"🗑 Удалено мусорных заданий: {stats['deleted']}")
print(f"✅ Осталось нормальных: {stats['kept']}")
