import requests, re, json, os, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
IMG_DIR = "questions/images_vpr"
os.makedirs(IMG_DIR, exist_ok=True)

# Обновлённые диапазоны ID (на основе дебага)
SUBDOMAINS = [
    ("rus2", "russian", 2, 52000, 54000),
    ("rus4", "russian", 4, 91000, 93000),
    ("rus5", "russian", 5, 92000, 94000),
    ("rus6", "russian", 6, 93000, 95000),
    ("rus7", "russian", 7, 94000, 96000),
    ("rus8", "russian", 8, 95000, 97000),
    ("rus10", "russian", 10, 96000, 98000),
    ("rus11", "russian", 11, 99000, 101000),  # расширенный диапазон
    ("math4", "math", 4, 100000, 101000),  # ПРАВИЛЬНЫЙ диапазон!
    ("math5", "math", 5, 100000, 101000),  # + 200000-201000 ниже
    ("math6", "math", 6, 101000, 102000),
    ("math7", "math", 7, 102000, 103000),
    ("math8", "math", 8, 103000, 104000),
    ("bio5", "biology", 5, 52500, 54500),
    ("bio6", "biology", 6, 53000, 55000),
    ("bio7", "biology", 7, 53500, 55500),
    ("bio8", "biology", 8, 54000, 56000),
    ("hist5", "history", 5, 51000, 53000),
    ("hist6", "history", 6, 51500, 53500),
    ("hist7", "history", 7, 52000, 54000),
    ("hist8", "history", 8, 52500, 54500),
    ("geo5", "geography", 5, 50000, 52000),
    ("geo6", "geography", 6, 50500, 52500),
    ("geo7", "geography", 7, 51000, 53000),
    ("geo8", "geography", 8, 51500, 53500),
    ("phys7", "physics", 7, 55000, 57000),
    ("phys8", "physics", 8, 55500, 57500),
    ("phys11", "physics", 11, 56000, 58000),
    ("eng4", "english", 4, 53000, 55000),
    ("eng7", "english", 7, 53500, 55500),
    ("eng11", "english", 11, 54000, 56000),
    ("soc6", "social", 6, 54500, 56500),
    ("soc7", "social", 7, 55000, 57000),
    ("soc8", "social", 8, 55500, 57500),
    ("soc9", "social", 9, 56000, 58000),
    ("chem8", "chemistry", 8, 57000, 59000),
    ("chem9", "chemistry", 9, 57500, 59500),
    ("chem11", "chemistry", 11, 58000, 60000),
    ("lit6", "literature", 6, 58500, 60500),
    ("lit7", "literature", 7, 59000, 61000),
    ("lit8", "literature", 8, 59500, 61500),
    ("lit9", "literature", 9, 60000, 62000),
    ("lit10", "literature", 10, 60500, 62500),
    ("lit11", "literature", 11, 61000, 63000),
    ("inf7", "informatics", 7, 61500, 63500),
    ("inf8", "informatics", 8, 62000, 64000),
    ("inf9", "informatics", 9, 62500, 64500),
    ("inf10", "informatics", 10, 63000, 65000),
    ("inf11", "informatics", 11, 63500, 65500),
    ("okr4", "okr", 4, 64000, 66000),
]

# Дополнительный диапазон для math5 (200000-201000)
MATH5_EXTRA = (200000, 201000)

JUNK = re.compile(r'(спиши\s+текст|под\s+диктовку|запиши\s+текст\s+под|внимательно\s+прочитай\s+и\s+спиши)', re.I)

session = requests.Session()
session.headers.update(UA)
lock = threading.Lock()

def clean_text(s):
    s = s.replace("\u00ad", "").replace("\xa0", " ")
    s = re.sub(r"Решения заданий с развернутым ответом.*?самостоятельно\.", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_test(base, html, seen):
    soup = BeautifulSoup(html, "html.parser")
    tasks = []
    for main in soup.find_all("div", class_="prob_maindiv"):
        did = main.get("data-id", "")
        if did in seen: continue
        body = main.find("div", class_="pbody")
        if not body: continue
        # Удаляем решения (solution) целиком
        for bad in body.find_all(class_=re.compile(r"solution")):
            bad.decompose()
        # Чистим minor от мусорных фраз, но оставляем формулировки заданий
        for minor in body.find_all(class_=re.compile(r"minor")):
            for p in minor.find_all("p"):
                txt = p.get_text(strip=True)
                if any(junk in txt.lower() for junk in ["решения заданий", "самостоятельно", "критерии оценивания", "баллы"]):
                    p.decompose()
        txt = clean_text(body.get_text(" "))
        if len(txt) < 20 or JUNK.search(txt): continue
        seen.add(did)
        imgs = []
        for img in body.find_all("img"):
            src = img.get("src") or ""
            if not src: continue
            src = urljoin(base, src)
            try:
                name = "sd_" + re.sub(r'[^A-Za-z0-9_.-]', '_', src.split("/")[-1])[:60]
                p = f"{IMG_DIR}/{name}"
                if not os.path.exists(p):
                    ir = session.get(src, timeout=30)
                    if ir.status_code == 200 and len(ir.content) > 500:
                        open(p, "wb").write(ir.content)
                    else: continue
                imgs.append(p)
            except Exception: pass
        tasks.append({"id": f"vpr_sd_{did}", "task_text": txt, "answer": "---",
                      "image": "", "all_images": imgs, "audio": "", "all_audios": [],
                      "topic": "sdamgia_vpr"})
    return tasks

def check_test_id(base, tid):
    try:
        r = session.get(f"{base}test?id={tid}", timeout=15)
        if r.status_code == 200 and "prob_maindiv" in r.text:
            r.encoding = "utf-8"
            return tid, r.text
    except Exception:
        pass
    return None, None

grand = 0
for sub, subj, grade, start_id, end_id in SUBDOMAINS:
    base = f"https://{sub}-vpr.sdamgia.ru/"
    print(f"\n{'='*60}")
    print(f"🚀 {sub} ({subj} {grade}): перебор ID {start_id}-{end_id}")
    print('='*60)
    
    found_tests = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_test_id, base, tid): tid for tid in range(start_id, start_id + 500)}
        for future in as_completed(futures):
            tid, html = future.result()
            if tid:
                found_tests.append((tid, html))
    
    # Для math5 добавляем второй диапазон
    if sub == "math5":
        print(f"   Дополнительный диапазон {MATH5_EXTRA[0]}-{MATH5_EXTRA[1]}...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_test_id, base, tid): tid for tid in range(MATH5_EXTRA[0], MATH5_EXTRA[0] + 500)}
            for future in as_completed(futures):
                tid, html = future.result()
                if tid:
                    found_tests.append((tid, html))
    
    if not found_tests:
        print(f"   ❌ Рабочих тестов не найдено")
        continue
    
    print(f"   ✅ Найдено тестов: {len(found_tests)}")
    
    seen_tasks = set()
    all_tasks = []
    for tid, html in found_tests[:15]:
        tasks = parse_test(base, html, seen_tasks)
        all_tasks.extend(tasks)
        print(f"   test {tid}: +{len(tasks)} | всего: {len(all_tasks)}")
        if len(all_tasks) >= 400: break
    
    if not all_tasks: continue
    
    out = f"questions/vpr_{subj}_{grade}.json"
    try:
        old = json.load(open(out))
        old_ids = {t["id"] for t in old}
        all_tasks = old + [t for t in all_tasks if t["id"] not in old_ids]
    except Exception: pass
    
    json.dump(all_tasks, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"   💾 {subj}_{grade}: {len(all_tasks)} задач")
    grand += len(all_tasks)

print(f"\n🎉 ИТОГО: {grand} задач со Сдамгии!")
