import json, os

# ID на удаление из 4 и 5 отчетов DeepSeek
remove_ids_raw = """
fipi_7D7448, fipi_B2864C, fipi_15274C, fipi_A53641, fipi_50AA4D, fipi_EC9E02, fipi_1EB20A, fipi_46511E, 
fipi_1D0119, fipi_13442E, fipi_626E20, fipi_0A7DAC, fipi_64FC99, fipi_120891, fipi_DEB890, fipi_B48F8A, 
fipi_14018E, fipi_CD1D80, fipi_9DE484, fipi_480A88, fipi_8E7C61, fipi_BB603A, fipi_CB6FE8, fipi_D96868, 
fipi_AF4F67, fipi_4B8D92, fipi_433A84, fipi_BD62B3, fipi_571AAB, fipi_663659, fipi_D67CAF, fipi_CC0498, 
fipi_CADC9A, fipi_5644DE, 647B00, 168D5C, 752477, 6962B1, EFA281, 5610DB, 2B5215, 148D6F, A90BD0, 
38F03F, CC5C01, 1B9E4A, 391F16, D41F17, DA80DE, 58AF4C, E5DDF6, 85B103, BA8D7C, 19ED26, A68CC2, 
42B0FF, F7193B, 40A06E, 617AF6, 57AF61, BE11C8, 26DB7F, ECC702, 6ABA0D, B305C3, 7AFCD3, 36F3FA
"""

# Нормализация ID
bad_ids = set()
for item in remove_ids_raw.replace('\n', ',').split(','):
    cid = item.strip()
    if cid:
        bad_ids.add(cid)
        if cid.startswith('fipi_'):
            bad_ids.add(cid[5:])
        else:
            bad_ids.add(f"fipi_{cid}")

print(f"🎯 Загружено {len(bad_ids)} вариантов масок ID на удаление (файлы 4 и 5).")

def clean_and_fix_file(fpath):
    if not os.path.exists(fpath):
        return
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            new_data = []
            removed = 0
            fixed = 0
            for t in data:
                if isinstance(t, dict):
                    tid = t.get('id', '')
                    if tid in bad_ids:
                        removed += 1
                        continue
                    # Ручной фикс конкретного задания с делением
                    if tid in ['fipi_0A3E4F', '0A3E4F']:
                        t['task_text'] = t.get('task_text', '').replace('1 3', '1/3')
                        fixed += 1
                    new_data.append(t)
            
            if removed > 0 or fixed > 0:
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                print(f"🧹 {os.path.basename(fpath)}: удалено {removed}, исправлено {fixed}.")
    except Exception as e:
        print(f"⚠️ Ошибка обработки {fpath}: {e}")

# Чистим скомпилированные CHECK файлы
for i in range(1, 6):
    for fn in [f"CHECK_{i}_tochnye.json", f"CHECK_{i}_OGE_estestvo.json", f"CHECK_{i}_OGE_guman.json", f"CHECK_{i}_EGE_estestvo.json", f"CHECK_{i}_EGE_guman.json"]:
        clean_and_fix_file(fn)

# Чистим исходники
if os.path.exists('questions'):
    for qf in os.listdir('questions'):
        if qf.endswith('.json'):
            clean_and_fix_file(os.path.join('questions', qf))

print("✨ Вторая часть чистки и фиксов завершена!")
