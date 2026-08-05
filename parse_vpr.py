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

CODE_MAP = {
    "MA": "math", "RU": "russian", "OKR": "okr",
    "LC": "literary", "LCHT": "literary", "LI": "literature", "LIT": "literature",
    "EN": "english", "DE": "german", "FR": "french",
    "IS": "history", "BI": "biology", "GG": "geography",
    "OB": "social", "SO": "social",
    "FI": "physics", "HI": "chemistry", "CH": "chemistry", "XI": "chemistry",
    "INF": "informatics",
}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"})

# --- Скрейбим страницу (ловит 2026+2027 и новые коды) ---
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

# --- Перебор URL за все 3 года (ловит 2025 и то, что страница скрыла) ---
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

def split_tasks(text, subj, grade, level, year):
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
        tasks.append({
            "id": f"vpr_{subj}_{grade}_{level}{year}_t{i}",
            "task_text": part[:3000],
            "image": "", "all_images": [],
            "audio": "", "all_audios": [],
            "answer": "---",
            "topic": f"vpr_{grade}_klass"
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
        print(f"✅ {fname}")
        with open(f"/tmp/vpr/{fname}", "wb") as f:
            f.write(r.content)
        text = ""
        with pdfplumber.open(f"/tmp/vpr/{fname}") as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        tasks = split_tasks(text, subj, grade, level, year)
        results.setdefault(key, []).extend(tasks)
        print(f"   → задач: {len(tasks)}")
    except Exception as e:
        print(f"⚠️ {fname}: {e}")
    time.sleep(0.25)

print("\n=== СОХРАНЕНИЕ (по классам!) ===")
total = 0
for key, tasks in results.items():
    if tasks:
        with open(f"questions/vpr_{key}.json", "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"💾 vpr_{key}: {len(tasks)}")
        total += len(tasks)
print(f"🎉 ВСЕГО: {total} задач ВПР с разбивкой по классам!")
