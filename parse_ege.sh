#!/bin/bash
cd /root/neuro-repetitor-bot
LOG="/root/neuro-repetitor-bot/ege_parse.log"
echo "=== Начало массового парсинга ЕГЭ: $(date) ===" > "$LOG"

# Список: proj_id  код  страниц  название
subjects=(
  "EA45D8517ABEB35140D0D83E76F14A41 chem_ege 80 Химия"
  "BA1F39653304A5B041B656915DC36B38 phys_ege 100 Физика"
  "AF0ED3F2557F8FFC4C06F80B6803FD26 russian_ege 100 Русский"
  "756DF168F63F9A6341711C61AA5EC578 social_ege 100 Обществознание"
  "4F431E63B9C9B25246F00AD7B5253996 ege_literature 80 Литература"
  "068A227D253BA6C04D0C832387FD0D89 history_ege 120 История"
  "4B53A6CB75B0B5E1427E596EB4931A2A ege_english 80 Английский"
  "B9ACA5BBB2E19E434CD6BEC25284C67F inf_ege 80 Информатика"
  "20E79180061DB32845C11FC7BD87C7C8 geo_ege 70 География"
  "CA9D848A31849ED149D382C32A7A2BE4 bio_ege 90 Биология"
)

for item in "${subjects[@]}"; do
  read -r proj code pages name <<< "$item"
  echo "" >> "$LOG"
  echo "=== [$name] старт: $(date) ===" >> "$LOG"
  python3 parse_fipi.py "$proj" "$code" "$pages" 2>&1 | tee -a "$LOG"
  systemctl restart neuro-repetitor
  echo "=== [$name] готово: $(date) ===" >> "$LOG"
done

echo "" >> "$LOG"
echo "=== ВСЕ ЕГЭ ГОТОВЫ: $(date) ===" >> "$LOG"
echo "" >> "$LOG"
echo "=== ИТОГОВАЯ СТАТИСТИКА ===" >> "$LOG"
for f in questions/*_ege.json questions/ege_*.json; do
  [ -f "$f" ] || continue
  count=$(python3 -c "import json; print(len(json.load(open('$f'))))" 2>/dev/null)
  echo "  $f: $count задач" >> "$LOG"
done
echo "=== КОНЕЦ ===" >> "$LOG"
