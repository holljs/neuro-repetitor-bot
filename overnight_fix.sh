#!/bin/bash
cd /root/neuro-repetitor-bot
echo "=== 1. Перепарс основных предметов ==="
python3 parse_sdamgia_v2.py
echo "=== 2. Перепарс языков/окр/био10 ==="
python3 parse_sdamgia_extra.py
echo "=== 3. Уникальные ID ==="
python3 - << 'EOF'
import json, glob, os, re
for jf in sorted(glob.glob('questions/vpr_*.json')):
    parts = os.path.basename(jf).replace('vpr_', '').replace('.json', '').split('_')
    if len(parts) < 2: continue
    subj, grade = parts[0], parts[1]
    tasks = json.load(open(jf))
    for t in tasks:
        if re.match(r'^vpr_sd_\d+$', t['id']):
            t['id'] = f'vpr_{subj}_{grade}_sd_' + t['id'].split('_')[-1]
    json.dump(tasks, open(jf, 'w'), ensure_ascii=False, indent=2)
print("✅ ID уникальны")
EOF
echo "=== 4. Авточистка брака ==="
python3 - << 'EOF'
import json, glob, os, re
removed = 0
for jf in sorted(glob.glob('questions/vpr_*.json')):
    tasks = json.load(open(jf))
    clean = []
    for t in tasks:
        txt = t['task_text']; imgs = t.get('all_images', []); auds = t.get('all_audios', [])
        bad = False
        if re.search(r'(ты\s+услышишь|прослушать\s+запись|you\s+will\s+hear|listen\s+to)', txt, re.I) and not auds: bad = True
        if re.search(r'рассмотрите\s+(рисунок|карту|изображ|схему|диаграмму|плакат)', txt, re.I) and not imgs: bad = True
        if re.search(r'^(текст\s+диктанта|спиши\s+текст)', txt, re.I): bad = True
        if bad: removed += 1
        else: clean.append(t)
    if len(clean) != len(tasks):
        json.dump(clean, open(jf, 'w'), ensure_ascii=False, indent=2)
print(f"🗑 Авточистка удалила: {removed}")
EOF
echo "=== ГОТОВО ==="
