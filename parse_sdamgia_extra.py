import requests, re, json, os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
IMG_DIR = "questions/images_vpr"
AUD_DIR = "questions/audio_vpr"
os.makedirs(AUD_DIR, exist_ok=True)

SUBS = [
    ("en4", "english", 4, 84600), ("en7", "english", 7, 673000), ("en11", "english", 11, 106000),
    ("de4", "german", 4, 2500), ("de7", "german", 7, 1), ("de11", "german", 11, 10000),
    ("fr4", "french", 4, 2000), ("fr7", "french", 7, 1000), ("fr11", "french", 11, 9500),
    ("nat4", "okr", 4, 345000), ("bio10", "biology", 10, 20000),
]

JUNK_RE = re.compile(r'(Решения заданий с развернутым ответом[^.]*\.|Запишите решение на бумаге\.|На следующей странице[^.]*\.|Развернуть|Свернуть|Показать целиком|Воспользуйтесь плеером[^.]*\.|Версия для печати[^.]*MS Word)', re.I)
LISTEN_RE = re.compile(r'(ты\s+услышишь|прослушать\s+запись|аудирование|you\s+will\s+hear|listen\s+to)', re.I)

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
        p = body.new_tag("p"); p.string = " // ".join(rows)
        table.replace_with(p)

def save_audio(src, base):
    src = urljoin(base, src)
    key = re.sub(r'[^A-Za-z0-9_.-]', '_', src.split("/")[-1])[:50]
    for ext in [".mp3", ".ogg", ".wav"]:
        p = f"{AUD_DIR}/sd_{key}{ext}"
        if os.path.exists(p): return p
    try:
        r = session.get(src, timeout=60)
        if r.status_code != 200 or len(r.content) < 1000: return None
        h = r.content[:4]
        ext = ".mp3" if (h[:3] == b'ID3' or h[0] == 0xFF) else ".ogg" if h == b'OggS' else ".wav" if h == b'RIFF' else ".mp3"
        p = f"{AUD_DIR}/sd_{key}{ext}"
        open(p, "wb").write(r.content)
        return p
    except Exception:
        return None

def save_image(src, base):
    src = urljoin(base, src)
    key = re.sub(r'[^A-Za-z0-9_.-]', '_', src.split("/")[-1])[:50]
    try:
        for ext in [".jpg", ".png"]:
            p = f"{IMG_DIR}/sd_{key}{ext}"
            if os.path.exists(p): return p
        ir = session.get(src, timeout=30)
        if ir.status_code != 200 or len(ir.content) < 500: return None
        h = ir.content[:8]
        ext = ".jpg" if h[:3] == b'\xff\xd8\xff' else ".png" if h[:4] == b'\x89PNG' else None
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
    tasks = []
    for main in soup.find_all("div", class_="prob_maindiv"):
        did = main.get("data-id", "")
        if did in seen: continue
        body = main.find("div", class_="pbody")
        if not body: continue
        auds = []
        for audio in body.find_all("audio"):
            s = audio.find("source")
            src = (s.get("src") if s else None) or audio.get("src") or ""
            if src:
                p = save_audio(src, base)
                if p: auds.append(p)
        imgs = []
        for img in body.find_all("img"):
            s = img.get("src") or ""
            if s:
                p = save_image(s, base)
                if p: imgs.append(p)
        tables_to_text(body)
        for bad in body.find_all(class_=re.compile(r"solution")): bad.decompose()
        txt = clean_text(body.get_text(" "))
        if len(txt) < 20: continue
        if LISTEN_RE.search(txt) and not auds: continue
        seen.add(did)
        tasks.append({"id": f"vpr_sd_{did}", "task_text": txt, "answer": "---",
                      "image": "", "all_images": imgs,
                      "audio": auds[0] if auds else "", "all_audios": auds,
                      "topic": "sdamgia_vpr"})
    return tasks

grand = 0
for sub, subj, grade, start_id in SUBS:
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
        na = sum(1 for t in uniq if t["all_audios"])
        ni = sum(1 for t in uniq if t["all_images"])
        print(f"   💾 {len(uniq)} задач (аудио: {na}, картинки: {ni})")
        grand += len(uniq)
print(f"\n🎉 ИТОГО допов: {grand} задач!")
