import json, os

raw_ids = """
fipi_59966A, fipi_4A8A38, fipi_BE8F6B, fipi_901369, fipi_173233, fipi_9F7F88, fipi_2180EE, fipi_641BE0, 
fipi_474768, fipi_A9E138, fipi_BA112C, fipi_DFDB21, fipi_D239D1, fipi_0B74A0, fipi_056598, fipi_70977E, 
fipi_77083C, fipi_6680EF, fipi_4F495A, fipi_22BE06, fipi_CC822B, fipi_3BBF34, fipi_43E7B4, fipi_28A462, 
fipi_B759B8, fipi_105A73, fipi_128F5C, fipi_FA5F44, fipi_44E161, fipi_FE8F9A, fipi_940C82, fipi_0C89A8, 
fipi_98B81F, fipi_970C86, fipi_A5F75F, fipi_553B89, fipi_C54D7C, fipi_353462, fipi_7401D0, fipi_0C18BF, 
fipi_DE5103, fipi_1E6AE0, fipi_3DC65A, fipi_0ED8A9, fipi_52EEEE, fipi_B30AA5, fipi_5E14EC, fipi_136FE2, 
fipi_E10D8D, fipi_9D4785, fipi_675692, fipi_65C092, fipi_4592E6, fipi_34D890, fipi_362E3F, fipi_811839, 
fipi_853538, fipi_09628F, fipi_0C878B, fipi_9DE7BD, fipi_67D7B0, fipi_15DCA5, fipi_9604A5, fipi_65ABA8, 
fipi_47D8C4, fipi_4B8BC2, fipi_53F1CD, fipi_504BC9, fipi_39E3E6, fipi_40966C, fipi_40F7D2, fipi_4CF966, 
fipi_FBBA60, fipi_B95633, fipi_1375EF, fipi_15AE47, fipi_090715, fipi_BAD281, fipi_B1B78D, fipi_095E1D, 
fipi_77101A, fipi_15551A, fipi_AB433D, fipi_AF223C, fipi_47E444, fipi_0CD247, fipi_B30645, fipi_201048, 
fipi_968A42, fipi_62C34C, fipi_EFC5F4, fipi_3233FD, fipi_F8AE06, fipi_021704, fipi_1BBA05, fipi_DDCC01, 
fipi_5BB60F, fipi_5FFF05, fipi_E3D6A8, fipi_B4DAA0, fipi_1836AF, fipi_A8E929, fipi_D2912F, fipi_4075D4, 
fipi_478EDF, fipi_2119D2, fipi_117323, fipi_173233, fipi_8C51C6, fipi_F3C654, fipi_F9662A
"""

bad_ids = set()
for item in raw_ids.replace('\n', ',').split(','):
    cid = item.strip()
    if cid:
        bad_ids.add(cid)
        if cid.startswith('fipi_'): bad_ids.add(cid[5:])

def clean_file(fpath):
    if not os.path.exists(fpath): return
    try:
        with open(fpath, 'r', encoding='utf-8') as f: data = json.load(f)
        if isinstance(data, list):
            new_data = [t for t in data if isinstance(t, dict) and t.get('id') not in bad_ids]
            removed = len(data) - len(new_data)
            if removed > 0:
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                print(f"🧹 {os.path.basename(fpath)}: вырезано {removed} задач.")
    except Exception as e: print(f"⚠️ Ошибка {fpath}: {e}")

for fn in ["CHECK_1_tochnye.json", "CHECK_1_REMAINING.json"]: clean_file(fn)
if os.path.exists('questions'):
    for qf in os.listdir('questions'):
        if qf.endswith('.json'): clean_file(os.path.join('questions', qf))

print("✨ Чистка завершена!")
