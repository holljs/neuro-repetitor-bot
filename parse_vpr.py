import json, re, time, os, sys
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote, quote
urllib3.disable_warnings()

try:
    import pdfplumber
except ImportError:
    print("❌ pip install pdfplumber"); sys.exit(1)

PAGE = "https://fioco.ru/obraztsi_i_opisaniya_vpr"
YEARS = [2025, 2026, 2027]
IMG_DIR = "questions/images_vpr"

CODE_MAP = {
    "MA": "math", "RU": "russian", "OKR": "okr",
    "LC": "literary", "LCHT": "literary", "LI": "literature", "LIT": "literature",
    "EN": "english", "DE": "german", "FR": "french",
    "IS": "history", "BI": "biology", "GG": "geography",
    "OB": "social", "SO": "social",
    "FI": "physics", "HI": "chemistry", "CH": "chemistry", "XI": "chemistry",
    "INF": "informatics",
}

# ✂️ Всё после этих заголовков — ОТРЕЗАЕМ (это ответы и критерии, не задания!)
CUT_RE = re.compile(r'(?im)^\s*(Ответы\s*$|Ответы\s+и|Критерии\s+оценивания|Система\s+оценивания|Ключи\s+|Правильные\s+ответы)')

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"})

pdf_links = []
try:
    r = session.get(PAGE, verify=False, timeout=30)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = unquote(a["href"])
        if ("ВПР_" in href or "ВПР-" in href) and ".pdf" in href.lower() and "DEMO" in href.upper():
            pdf_links.append(urljoin(PAGE, a["href"]))
except Exception as e:
    print(f"⚠️ Страница не читается: {e}")
print(f"📄 Со страницы: {len(pdf_links)} PDF")

for year in YEARS:
    for folder in [f"ВПР_{year}", f"ВПР-{year}"]:
        for code in CODE_MAP:
            for grade in [4, 5, 6, 7, 8, 10, 11]:
                for lvl in ["", "(B)", "(U)"]:
                    if lvl and grade in (4, 5):
                        continue
                    s = f"_{lvl}" if lvl else ""
                    pdf_links.append(f"https://fioco.ru/Media/Default/Documents/{quote(folder + '/')}VPR_{code}-{grade}_DEMO{s}_{year}.pdf")

results = {}
os.makedirs("/tmp/vpr", exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

def norm(s):
    return re.sub(r'\s+', ' ', s)

def split_tasks(text):
    tasks = []
    parts = re.split(r'(?m)^(?=Задание\s+\d{1,2})', text)
    if len(parts) < 3:
        parts = re.split(r'(?m)^(?=\d{1,2}[.\)])', text)
    for i, part in enumerate(parts):
        part = part.strip()
        if len(part) < 40:
            continue
        if not re.match(r'(Задание\s+)?\d{1,2}[.\)]?', part):
            continue
        #  фильтр огрызков критериев
        if re.search(r'(баллов|оценивается|допущено\s+более)', part) and 'Задание' not in part and len(part) < 400:
            continue
        tasks.append({
            "id": f"tmp_{i}",
            "task_text": part[:3000],
            "image": "", "all_images": [],
            "audio": "", "all_audios": [],
            "answer": "---",
        })
    return tasks

seen = set()
for url in pdf_links:
    fname = unquote(url.split("/")[-1])
    if fname in seen:
        continue
    m = re.match(r"VPR_([A-Z]+)-(\d+)_DEMO(?:_\(([BU])\))?_(\d{4})", fname)
    if not m:
        continue
    seen.add(fname)
    code, grade, level, year = m.group(1), m.group(2), (m.group(3) or ""), m.group(4)
    subj = CODE_MAP.get(code)
    if not subj:
        continue
    key = f"{subj}_{grade}"
    try:
        r = session.get(url, verify=False, timeout=30)
        if r.status_code != 200 or b"%PDF" not in r.content[:20]:
            continue
        tmp = f"/tmp/vpr/{fname}"
        with open(tmp, "wb") as f:
            f.write(r.content)
        with pdfplumber.open(tmp) as pdf:
            pages_text = [(p.extract_text() or "") for p in pdf.pages]
        full = "\n".join(pages_text)
        cm = CUT_RE.search(full)
        if cm:
            full = full[:cm.start()]
        tasks = split_tasks(full)
        base = re.sub(r'[^A-Za-z0-9_-]', '_', fname[:-4])
        needed = {}
        for t in tasks:
            snip = norm(t["task_text"])[:40]
            for idx, pt in enumerate(pages_text):
                if snip and snip in norm(pt):
                    t["all_images"] = [f"{IMG_DIR}/{base}_p{idx+1}.jpg"]
                    t["id"] = f"vpr_{subj}_{grade}_{level}{year}_t{len(results.get(key, []))}_{idx}"
                    t["topic"] = f"vpr_{grade}_klass"
                    needed[idx] = True
                    break
        if needed:
            with pdfplumber.open(tmp) as pdf:
                for idx in needed:
                    ppath = f"{IMG_DIR}/{base}_p{idx+1}.jpg"
                    if not os.path.exists(ppath):
                        try:
                            pdf.pages[idx].to_image(resolution=100).save(ppath, format="JPEG", quality=70)
                        except Exception as e:
                            print(f"⚠️ render: {e}")
        results.setdefault(key, []).extend(tasks)
        print(f"✅ {fname} → задач: {len(tasks)}, страниц с картинками: {len(needed)}")
    except Exception as e:
        print(f"⚠️ {fname}: {e}")
    time.sleep(0.25)

print("\n=== СОХРАНЕНИЕ ===")
total = 0
for key, tasks in results.items():
    if tasks:
        with open(f"questions/vpr_{key}.json", "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"💾 vpr_{key}: {len(tasks)}")
        total += len(tasks)
print(f"🎉 ВСЕГО: {total} задач ВПР (чистые задания + картинки страниц)!")
