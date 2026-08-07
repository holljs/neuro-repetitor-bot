import pdfplumber, json, re, os, requests
from urllib.parse import quote
import urllib3
urllib3.disable_warnings()

def clean_lines(text):
    out = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s: continue
        if re.search(r'(©\s*20\d\d|Федеральная служба|Код\s*$|Образец\s*$|ВПР\.\s|Проверочная работа по|Пояснение к)', s): continue
        out.append(s)
    return "\n".join(out)

def reading_text_from_pdf(path):
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages[:3]]
    full = clean_lines("\n".join(pages))
    m = re.search(r'\(1\)', full)
    if m:
        cand = full[m.start():]
    else:
        blocks = re.split(r'\n(?=Задание|\d{1,2}[.\)])', full)
        cand = max(blocks, key=len) if blocks else ""
        if len(cand) < 400: return ""
    cut = re.search(r'\n(Задание\s*\d|1\)\s*(Выполните|Найдите|Выпишите)|Ответ:)', cand[20:])
    if cut: cand = cand[:cut.start() + 20]
    return cand.strip()

def get_pdf(code, grade, year):
    os.makedirs("/tmp/vpr", exist_ok=True)
    path = f"/tmp/vpr/VPR_{code}-{grade}_DEMO_{year}.pdf"
    if os.path.exists(path): return path
    for folder in [f"ВПР_{year}", f"ВПР-{year}"]:
        url = f"https://fioco.ru/Media/Default/Documents/{quote(folder + '/')}VPR_{code}-{grade}_DEMO_{year}.pdf"
        try:
            r = requests.get(url, verify=False, timeout=30)
            if r.status_code == 200 and b"%PDF" in r.content[:20]:
                with open(path, "wb") as f: f.write(r.content)
                return path
        except Exception: pass
    return None

CODES = {"russian": ["RU"], "literature": ["LI"], "literary": ["LC", "LCHT"], "lcht": ["LCHT", "LC"]}
rt_cache = {}
stats = {"texts": 0, "imgs": 0}

for jf in sorted(os.listdir("questions")):
    if not jf.startswith("vpr_") or not jf.endswith(".json"): continue
    subj = jf[4:-5]
    codes = None
    for k in CODES:
        if subj.startswith(k): codes = CODES[k]; break
    tasks = json.load(open(f"questions/{jf}"))
    for t in tasks:
        if t.get("all_images"):
            t["all_images"] = []
            stats["imgs"] += 1
        if codes:
            my = re.search(r"_(20\d\d)_", t["id"]); year = my.group(1) if my else "2027"
            mg = re.search(r"vpr_[a-z]+_(\d+)", t["id"]); grade = mg.group(1)
            key = (codes[0], grade, year)
            if key not in rt_cache:
                rt = ""
                for code in codes:
                    p = get_pdf(code, grade, year)
                    if p: rt = reading_text_from_pdf(p)
                    if rt: break
                rt_cache[key] = rt
            rt = rt_cache[key]
            if rt and rt[:60] not in t["task_text"]:
                t["task_text"] = rt + "\n\n" + t["task_text"]
                stats["texts"] += 1
    json.dump(tasks, open(f"questions/{jf}", "w"), ensure_ascii=False, indent=2)
print(f"✅ Скриншотов страниц убрано: {stats['imgs']} | текстов приклеено: {stats['texts']}")
