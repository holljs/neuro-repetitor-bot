import requests, re, json, os, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
IMG_DIR = "questions/images_vpr"
os.makedirs(IMG_DIR, exist_ok=True)

SUBDOMAINS = [
    ("rus2", "russian", 2, 52000), ("rus4", "russian", 4, 91000),
    ("rus5", "russian", 5, 92000), ("rus6", "russian", 6, 93000),
    ("rus7", "russian", 7, 94000), ("rus8", "russian", 8, 95000),
    ("rus10", "russian", 10, 96000),
    ("math4", "math", 4, 100000), ("math5", "math", 5, 100000),
    ("math6", "math", 6, 101000), ("math7", "math", 7, 102000),
    ("math8", "math", 8, 103000),
    ("bio5", "biology", 5, 52500), ("bio6", "biology", 6, 53000),
    ("bio7", "biology", 7, 53500), ("bio8", "biology", 8, 54000),
    ("hist5", "history", 5, 51000), ("hist6", "history", 6, 51500),
    ("hist7", "history", 7, 52000), ("hist8", "history", 8, 52500),
    ("geo5", "geography", 5, 50000), ("geo6", "geography", 6, 50500),
    ("geo7", "geography", 7, 51000), ("geo8", "geography", 8, 51500),
    ("phys7", "physics", 7, 55000), ("phys8", "physics", 8, 55500),
    ("phys11", "physics", 11, 56000),
    ("eng4", "english", 4, 53000), ("eng7", "english", 7, 53500),
    ("soc6", "social", 6, 54500), ("soc7", "social", 7, 55000),
    ("soc8", "social", 8, 55500),
    ("chem8", "chemistry", 8, 57000), ("chem11", "chemistry", 11, 58000),
    ("lit6", "literature", 6, 58500), ("lit7", "literature", 7, 59000),
    ("lit8", "literature", 8, 59500),
    ("inf7", "informatics", 7, 61500), ("inf8", "informatics", 8, 62000),
    ("math10", "math", 10, 104000), ("bio10", "biology", 10, 54500),
    ("geo10", "geography", 10, 52000), ("lit10", "literature", 10, 60000),
]

JUNK_RE = re.compile(r'(Решения заданий с развернутым ответом[^.]*\.|Запишите решение на бумаге\.|На следующей странице[^.]*\.|Развернуть|Свернуть|Показать целиком)', re.I)
DICT_RE = re.compile(r'(текст\s+диктанта|спиши\s+текст|запиши\s+текст\s+под\s+диктовку)', re.I)
REF_RE = re.compile(r'(по\s+тексту|из\s+текста|текста\s*1|абзац|опираясь\s+на\s+текст|прочитайте\s+текст|прочитай\s+текст|выпиши.*предложени|из\s+первого\s+предложени)', re.I)
IMGREF_RE = re.compile(r'(фото|рисунк|изображ|знак[а-я]?|схем|диаграмм|буквой|над\s+буквой)', re.I)

session = requests.Session()
session.headers.update(UA)

def clean_text(s):
    s = s.replace("\u00ad", "").replace("\xa0", " ")
    s = JUNK_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()

def tables_to_text(body):
    for table in body.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if cells: rows.append(" | ".join(cells))
        p = body.new_tag("p")
        p.string = " // ".join(rows)
        table.replace_with(p)

def save_image(src, base):
    src = urljoin(base, src)
    key = re.sub(r'[^A-Za-z0-9_.-]', '_', src.split("/")[-1])[:50]
    try:
        for ext in [".jpg", ".png"]:
            p = f"{IMG_DIR}/sd_{key}{ext}"
            if os.path.exists(p): return p
        ir = session.get(src, timeout=30)
        if ir.status_code != 200 or len(ir.content) < 500: return None
        head = ir.content[:8]
        ext = ".jpg" if head[:3] == b'\xff\xd8\xff' else ".png" if head[:4] == b'\x89PNG' else None
        if not ext: return None
        p = f"{IMG_DIR}/sd_{key}{ext}"
        open(p, "wb").write(ir.content)
        return p
    except Exception:
        return None

def check_id(base, tid):
    try:
        r = session.get(f"{base}test?id={tid}", timeout=15)
        if r.status_code == 200 and "prob_maindiv" in r.text:
            r.encoding = "utf-8"
            return tid, r.text
    except Exception: pass
    return None, None

def parse_test(base, html, seen):
    soup = BeautifulSoup(html, "html.parser")
    # 1) Общий скрытый текст (Текст 1)
    common = ""
    for main in soup.find_all("div", class_="prob_maindiv"):
        body = main.find("div", class_="pbody")
        if not body: continue
        t = body.get_text(" ")
        if re.search(r'\(\d+\)', t) and len(t) > 500 and len(t) > len(common):
            common = clean_text(t)
    # 2) Задания
    tasks = []
    last_imgs = []
    for main in soup.find_all("div", class_="prob_maindiv"):
        did = main.get("data-id", "")
        if did in seen: continue
        body = main.find("div", class_="pbody")
        if not body: continue
        # КАРТИНКИ ПЕРВЫМИ (из скрытых блоков и из таблиц!)
        own_imgs = []
        for img in body.find_all("img"):
            s = img.get("src") or ""
            if s:
                p = save_image(s, base)
                if p: own_imgs.append(p)
        tables_to_text(body)
        for bad in body.find_all(class_=re.compile(r"solution")): bad.decompose()
        txt = clean_text(body.get_text(" "))
        if len(txt) < 20 or DICT_RE.search(txt): continue
        if common and common[:80] not in txt and REF_RE.search(txt):
            txt = common + " " + txt
        # Свои картинки ИЛИ из предыдущего задания (1.1 -> 1.2)
        imgs = own_imgs
        if not imgs and IMGREF_RE.search(txt) and last_imgs:
            imgs = last_imgs
        if own_imgs:
            last_imgs = own_imgs
        seen.add(did)
        tasks.append({"id": f"vpr_sd_{did}", "task_text": txt, "answer": "---",
                      "image": "", "all_images": imgs, "audio": "", "all_audios": [],
                      "topic": "sdamgia_vpr"})
    return tasks

grand = 0
for sub, subj, grade, start_id in SUBDOMAINS:
    base = f"https://{sub}-vpr.sdamgia.ru/"
    print(f"\n🚀 {sub} ({subj} {grade})")
    found = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(check_id, base, t): t for t in range(start_id, start_id + 1000, 2)}
        for f in as_completed(futs):
            tid, html = f.result()
            if tid: found.append((tid, html))
    if not found:
        print("   ❌ тестов нет"); continue
    seen, all_tasks = set(), []
    for tid, html in found[:30]:
        all_tasks += parse_test(base, html, seen)
    uniq, hashes = [], set()
    for t in all_tasks:
        h = re.sub(r'\s+', ' ', t["task_text"][:300])
        if h not in hashes:
            hashes.add(h); uniq.append(t)
    if uniq:
        json.dump(uniq, open(f"questions/vpr_{subj}_{grade}.json", "w"), ensure_ascii=False, indent=2)
        with_img = sum(1 for t in uniq if t["all_images"])
        print(f"   💾 {len(uniq)} задач (с картинками: {with_img})")
        grand += len(uniq)
print(f"\n🎉 ИТОГО: {grand} задач!")
