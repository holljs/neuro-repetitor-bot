#!/bin/bash
cd /root/neuro-repetitor-bot
LOG="/root/neuro-repetitor-bot/langs_parse.log"
echo "=== Начало парсинга языков: $(date) ===" > "$LOG"

subjects=(
  "5BAC840990A3AF0A4EE80D1B5A1F9527 ege_french 60 Французский_ЕГЭ"
  "B5963A8D84CF9020461EAE42F37F541F ege_german 60 Немецкий_ЕГЭ"
  "F6298F3470D898D043E18BC680F60434 ege_chinese 60 Китайский_ЕГЭ"
  "E040A72A1A3DABA14C90C97E0B6EE7DC math_base_ege 150 Математика_база_ЕГЭ"
  "8C65A335D93D9DA047C42613F61416F3 ege_spanish 60 Испанский_ЕГЭ"
  "2A4C52ED5AC1ADA644B8BBF169FEC0FC oge_french 60 Французский_ОГЭ"
  "A2AC67AE354EBC5242C49482CBC13451 oge_german 60 Немецкий_ОГЭ"
  "7FF0B02E53DFBCDE4F56B0148BE9A236 oge_spanish 60 Испанский_ОГЭ"
)

for item in "${subjects[@]}"; do
  read -r proj code pages name <<< "$item"
  echo "" >> "$LOG"
  echo "=== [$name] старт: $(date) ===" >> "$LOG"
  python3 parse_fipi.py "$proj" "$code" "$pages" 2>&1 | tee -a "$LOG"
  echo "=== [$name] готово: $(date) ===" >> "$LOG"
done

systemctl restart neuro-repetitor

echo "" >> "$LOG"
echo "=== ВСЕ ЯЗЫКИ ГОТОВЫ: $(date) ===" >> "$LOG"
for f in questions/ege_french.json questions/ege_german.json questions/ege_chinese.json questions/math_base_ege.json questions/ege_spanish.json questions/oge_french.json questions/oge_german.json questions/oge_spanish.json; do
  [ -f "$f" ] || continue
  count=$(python3 -c "import json; print(len(json.load(open('$f'))))" 2>/dev/null)
  echo "  $f: $count задач" >> "$LOG"
done
echo "=== КОНЕЦ ===" >> "$LOG"
