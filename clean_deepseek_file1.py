import json, os

# Полный список ID из ответа DeepSeek (первый файл)
raw_ids = """
q097E41, 097E41, q54924B, 54924B, q5D3C40, 5D3C40, q3CC449, 3CC449, q9C31C3, 9C31C3, 
qE34C05, E34C05, qFA8C9C, FA8C9C, qF80913, F80913, qF4AE13, F4AE13, qF0091E, F0091E, 
qFE8A19, FE8A19, q07781B, 07781B, q0CA31E, 0CA31E, q061A18, 061A18, q71EE14, 71EE14, 
q79A610, 79A610, qBB6210, BB6210, qB1CA1D, B1CA1D, qB2201A, B2201A, qB59F1A, B59F1A, 
qB77C16, B77C16, q150B1F, 150B1F, q1B8B19, 1B8B19, q1C761E, 1C761E, q14A018, 14A018, 
q2E2E14, 2E2E14, q2CFE17, 2CFE17, q21F913, 21F913, q219613, 219613, q25AE18, 25AE18, 
q273818, 273818, qD8DE10, D8DE10, qD07B18, D07B18, q53C614, 53C614, q520F13, 520F13, 
qA4B517, A4B517, qAF7118, AF7118, qC4F011, C4F011, qC33B1E, C33B1E, q9AB210, 9AB210, 
q9DA310, 9DA310, q95FA1B, 95FA1B, q916711, 916711, q94FE12, 94FE12, q981215, 981215, 
q934816, 934816, qEEC21F, EEC21F, qEF0911, EF0911, qE46411, E46411, qEA0419, EA0419, 
qECCC13, ECCC13, q68AB10, 68AB10, q6D8017, 6D8017, q68001C, 68001C, q63AD19, 63AD19, 
q32AB12, 32AB12, q3B531C, 3B531C, q36C01E, 36C01E, q32F618, 32F618, q806C14, 806C14, 
q8FF426, 8FF426, q8A6326, 8A6326, q81A41C, 81A41C, q4A1F2B, 4A1F2B, q418E22, 418E22, 
q4B9B29, 4B9B29, qF6882F, F6882F, qF9A32A, F9A32A, qF4CC28, F4CC28, q06AC29, 06AC29, 
q7ADF27, 7ADF27, q76122A, 76122A, q76A62C, 76A62C, qBB8327, BB8327, qB41B2B, B41B2B, 
qBC1F2C, BC1F2C, q12A02F, 12A02F, q171D20, 171D20, q1A812B, 1A812B, q173A22, 173A22, 
q199525, 199525, q103326, 103326, q28B325, 28B325, q2C832A, 2C832A, qD0D22F, D0D22F, 
qDEB12D, DEB12D, qDB3225, DB3225, qD5802A, D5802A, qDDAD2E, DDAD2E, qD20CD3, D20CD3, 
q51F124, 51F124, q5F2721, 5F2721, q55322A, 55322A, q58DB2C, 58DB2C, qAB9727, AB9727, 
qA81C2A, A81C2A, qCAC621, CAC621, qC45525, C45525, qCA8E29, CA8E29, qC0C526, C0C526, 
q912224, 912224, q96A124, 96A124, q931C20, 931C20, q98802B, 98802B, q9CEB2A, 9CEB2A, 
q973F29, 973F29, qE7732F, E7732F, qE65720, E65720, qEA4E23, EA4E23, q65A424, 65A424, 
q681C2E, 681C2E, q6EB023, 6EB023, q38B020, 38B020, q3CD425, 3CD425, q331D29, 331D29, 
q880BD7, 880BD7, q89C3D3, 89C3D3, q4093C4, 4093C4, q47DAC6, 47DAC6, qF81BCF, F81BCF, 
qF932CB, F932CB, qF2B0C5, F2B0C5, q0630C4, 0630C4, q0BBBCB, 0BBBCB, q7E4CCF, 7E4CCF, 
q7477C0, 7477C0, q7435CB, 7435CB, q7643C1, 7643C1, q7134CE, 7134CE, qB6E3CB, B6E3CB, 
qB073C5, B073C5, q1D51CF, 1D51CF, q1527C7, 1527C7, q1790CC, 1790CC, q264CC0, 264CC0, 
q2CA8C0, 2CA8C0, qDE7AC9, DE7AC9, q52D8C1, 52D8C1, q5820CD, 5820CD, q5DE6C3, 5DE6C3, 
qA9D8C0, A9D8C0, q432550, 432550, q40F35B, 40F35B, q4DD651, 4DD651, q43475D, 43475D, 
q49215A, 49215A, q45B659, 45B659, q406A53, 406A53, q40FF58, 40FF58, qFD4058, FD4058, 
q0C275B, 0C275B, q0FB852, 0FB852, q05EE5C, 05EE5C, q0B1558, 0B1558, q7A8250, 7A8250, 
q7EE15B, 7EE15B, q7F1E51, 7F1E51, qB8D35A, B8D35A, qBD255E, BD255E, qB04F56, B04F56, 
qBF8E53, BF8E53, q1B7550, 1B7550, q14C45C, 14C45C, q1BA058, 1BA058, q283154, 283154, 
q2B335C, 2B335C, q2B9358, 2B9358, qD06250, D06250, qDF4D5B, DF4D5B, qDF7B5C, DF7B5C, 
qDFEC59, DFEC59, qD1DC53, D1DC53, q530C50, 530C50, q510B5D, 510B5D, q5C0C5A, 5C0C5A, 
q521C5A, 521C5A, q564758, 564758, qA97C55, A97C55, qA6FF59, A6FF59, qCD5252, CD5252, 
qCE4555, CE4555, qC03CA1, C03CA1, qCAB6AD, CAB6AD, q94CFA6, 94CFA6, q98E6A3, 98E6A3, 
q93DEA8, 93DEA8, q94ADA8, 94ADA8, qE4E4A6, E4E4A6, q648BA1, 648BA1, q6BFAAA, 6BFAAA, 
q351EAF, 351EAF, q34CDAF, 34CDAF, q3CEAAF, 3CEAAF, q32C5AB, 32C5AB, q3642AA, 3642AA, 
q3F99AC, 3F99AC, q35B3A3, 35B3A3, q4093C4, 4093C4, qF81BCF, F81BCF, qF932CB, F932CB, 
qF2B0C5, F2B0C5, q0630C4, 0630C4, q0BBBCB, 0BBBCB, q7E4CCF, 7E4CCF, q7477C0, 7477C0, 
q7435CB, 7435CB, q7643C1, 7643C1, q7134CE, 7134CE, qB6E3CB, B6E3CB, qB073C5, B073C5, 
q1D51CF, 1D51CF, q1527C7, 1527C7, q1790CC, 1790CC, q264CC0, 264CC0, q2CA8C0, 2CA8C0, 
qDE7AC9, DE7AC9, q52D8C1, 52D8C1, q5820CD, 5820CD, q5DE6C3, 5DE6C3, qA9D8C0, A9D8C0
"""

bad_ids = set()
for item in raw_ids.replace('\n', ',').split(','):
    cid = item.strip()
    if cid:
        bad_ids.add(cid)
        if cid.startswith('fipi_'):
            bad_ids.add(cid[5:])
        elif cid.startswith('q'):
            bad_ids.add(cid[1:])
            bad_ids.add(f"fipi_{cid}")
            bad_ids.add(f"fipi_{cid[1:]}")
        else:
            bad_ids.add(f"fipi_{cid}")
            bad_ids.add(f"q{cid}")

print(f"🎯 Сформировано {len(bad_ids)} масок ID на чистку.")

def clean_file(fpath):
    if not os.path.exists(fpath): return
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            initial_len = len(data)
            new_data = [t for t in data if isinstance(t, dict) and t.get('id') not in bad_ids]
            removed = initial_len - len(new_data)
            if removed > 0:
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                print(f"🧹 {os.path.basename(fpath)}: вырезано {removed} битых задач.")
    except Exception as e:
        print(f"⚠️ Ошибка {fpath}: {e}")

# 1. Очищаем сводные файлы
clean_file("CHECK_1_tochnye.json")

# 2. Очищаем исходники
if os.path.exists('questions'):
    for qf in os.listdir('questions'):
        if qf.endswith('.json'):
            clean_file(os.path.join('questions', qf))

print("✨ Чистка первого файла завершена!")
