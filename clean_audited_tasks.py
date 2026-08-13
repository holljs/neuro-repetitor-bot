import json, os

# Полный список ID на удаление из отчетов DeepSeek (1, 2 и 3)
remove_ids_raw = """
q0D6CFB, qD7FAF0, q9CE3F5, qEA97FD, qE47CF9, q3ee3FD, q3E6C4D, q9C7608, q3D8305, q3CFD06, 
q8B720C, q826109, q48A97F, q47C17B, qFE1D7F, qF5A07D, qFA317A, q791E76, q125474, qD50977, 
qDC1A78, q595071, qABF37B, q9ABE05, q0AB21E, q755317, q7C8E12, q77FF1D, q7A4416, qB51C1F, 
qBe2D18, q1AD315, q2B1812, qD29A1B, qD5C915, qDDB21C, q5B061D, qA3D111, qA43015, q93361B, 
q95A51D, qECCE1D, qE47B1E, qE6DF13, q680212, q6A171A, q6D761E, q658318, q8ECA1A, q415D28, 
qF4C72A, qF0BF23, qBF8B20, q1E702A, q2AD521, q22A925, qDA4522, qD15322, q525C2B, qA79824, 
qC85929, q9CED21, qEB5527, qEB892C, q684A20, q68BC21, q35312A, q82332D, q85D32C, q4844DF, 
qFFD9D6, q7157DC, qB741D0, qB42DDA, q19CADA, q223AD0, qD498D4, q56E2D5, q514cD3, qc013D0, 
qE974DF, qEBE4D0, qEC01DB, qE3A4D6, q67A7D4, q6A56DC, q3A0BD4, q3EACD1, q34CAD3, q842CD9, 
qF57859, q002650, qB14254, q2B3453, qDDB35B, qD90352, qD38C5A, q5B685F, q515950, q5D285A, 
qAE905F, qA08D56, q959156, qE10E5F, q3A2D5F, q339257, q3BF556, q8C305F, qF34AAF, qF7A4AC, 
qFA30A3, q76D2A4, q7E3EA9, qBF33A4, qBD2AA5, q190EAC, q1E8AA8, q2E31AB,
fipi_q7367BF, fipi_qD375BC, fipi_qB9E816, fipi_q3D562C, fipi_q4BBC54, fipi_q9AEB60,
fipi_90F26B, fipi_47D4F3, fipi_9E7E93, fipi_9D1661,
q7367BF, qD375BC, qB9E816, q3D562C, q4BBC54, q9AEB60, 90F26B, 47D4F3, 9E7E93, 9D1661
"""

# Нормализуем сет удаляемых ID (с префиксами fipi_ и без)
bad_ids = set()
for item in remove_ids_raw.replace('\n', ',').split(','):
    cid = item.strip()
    if cid:
        bad_ids.add(cid)
        if cid.startswith('fipi_'):
            bad_ids.add(cid[5:])
        else:
            bad_ids.add(f"fipi_{cid}")

print(f"🎯 Загружено {len(bad_ids)} вариантов масок ID на удаление.")

def clean_file(fpath):
    if not os.path.exists(fpath):
        return
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            new_data = [t for t in data if isinstance(t, dict) and t.get('id') not in bad_ids]
            removed = len(data) - len(new_data)
            if removed > 0:
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                print(f"🧹 {os.path.basename(fpath)}: удалено {removed} битых задач.")
    except Exception as e:
        print(f"⚠️ Ошибка обработки {fpath}: {e}")

# 1. Чистим файлы CHECK_*.json
for i in range(1, 6):
    for fn in [f"CHECK_{i}_tochnye.json", f"CHECK_{i}_OGE_estestvo.json", f"CHECK_{i}_OGE_guman.json", f"CHECK_{i}_EGE_estestvo.json", f"CHECK_{i}_EGE_guman.json"]:
        clean_file(fn)

# 2. Чистим исходники в папке questions/
if os.path.exists('questions'):
    for qf in os.listdir('questions'):
        if qf.endswith('.json'):
            clean_file(os.path.join('questions', qf))

print("✨ Чистка завершена!")
