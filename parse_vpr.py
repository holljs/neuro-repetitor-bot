import json, re, time, os, sys, base64
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote, quote
from dotenv import load_dotenv
urllib3.disable_warnings()
load_dotenv()
import pdfplumber

TR_TOKEN = os.getenv("TOKENROUTER_API_TOKEN")
if not TR_TOKEN:
    print("❌ TOKENROUTER_API_TOKEN не найден"); sys.exit(1)

TEST_MODE = "--test" in sys.argv
PAGE = "https://fioco.ru/obraztsi_i_opisaniya_vpr"
YEARS = [2025, 2026, 2027]
IMG_DIR = "questions/images_vpr"

CODE_MAP = {
    "MA": "math",
    "RU": "russian",
    "OKR": "okr",
    "LC": "literary",
    "LCHT": "literary",
    "LI": "literature",
    "LIT": "literature",
    "EN": "english",
    "DE": "german",
    "FR": "french",
    "IS": "history",
    "BI": "biology",
    "GG": "geography",
    "OB": "social",
    "SO": "social",
    "FI": "physics",
    "HI": "chemistry",
    "CH": "chemistry",
    "XI": "chemistry",
    "INF": "informatics",
}

VISION_PROMPT = (
    "Ты — точный парсер школьных заданий ВПР. Посмотри на изображение страницы.\n"
    "Верни СТРОГО валидный JSON без markdown-обёрток (без ```json):\n"
    '{"blocks": [{"num": <номер задания int или null>, "text": "<текст>", "answer": "<ответ>"}]}\n'
    "ПРАВИЛА: копируй дословно; игнорируй ©/«Федеральная служба»/«Код»/«Образец»; "
    "НЕ извлекай «Ответы»/«Критерии»; если заданий нет — {\"blocks\": []}; "
    "формулы в LaTeX: $\\frac{1}{2}$, $x^2$."
)

def parse_json_safe(s):
    s = s.strip()
    s = re.sub(r'^```(?:json)?\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    m = re.search(r'\{.*\}', s, re.DOTALL)
    if not m:
        raise Exception(f"нет JSON: {s[:200]}")
    raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw = re.sub(r'(?<!\\)\\(?![ntrfb"\\])', r'\\\\', raw)
        return json.loads(raw)

def ask_vision(data_uri):
    headers = {"Authorization": f"Bearer {TR_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "model": "qwen/qwen3.7-plus",
        "messages": [
            {"role": "system", "content": "Отвечай только валидным JSON без markdown-обёрток."},
            {"role": "user", "content": [
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": data_uri}}
            ]}
        ],
        "max_tokens": 4000,
        "temperature": 0.1
    }
    r = requests.post("https://api.tokenrouter.com/v1/chat/completions", json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    content = (msg.get("content") or msg.get("reasoning") or "").strip()
    if not content:
        raise Exception("пустой ответ")
    return parse_json_safe(content), content

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

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
    print(f"⚠️ Страница: {e}")

for year in YEARS:
    for folder in [f"ВПР_{year}", f"ВПР-{year}"]:
        for code in CODE_MAP:
            for grade in [4, 5, 6, 7, 8, 10, 11]:
                for lvl in ["", "(B)", "(U)"]:
                    if lvl and grade in (4, 5):
                        continue
                    s = f"_{lvl}" if lvl else ""
                    pdf_links.append(f"https://fioco.ru/Media/Default/Documents/{quote(folder + '/')}VPR_{code}-{grade}_DEMO{s}_{year}.pdf")

if TEST_MODE:
    pdf_links = [u for u in pdf_links if any(x in u for x in ["MA-7_DEMO_(B)_2027", "FI-7_DEMO_2027", "IS-5_DEMO_2027", "GG-5_DEMO_2027"])][:4]
    print(f"🧪 ТЕСТ: {len(pdf_links)} PDF")
else:
    print(f"📄 Всего PDF: {len(pdf_links)}")

results = {}
os.makedirs("/tmp/vpr", exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

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
        print(f"\n=== {fname} ===")
        r = session.get(url, verify=False, timeout=30)
        if r.status_code != 200 or b"%PDF" not in r.content[:20]:
            print("   пропуск: не PDF")
            continue
        tmp = f"/tmp/vpr/{fname}"
        with open(tmp, "wb") as f:
            f.write(r.content)
        base = re.sub(r'[^A-Za-z0-9_-]', '_', fname[:-4])

        with pdfplumber.open(tmp) as pdf:
            total_pages = len(pdf.pages)
            cut_page = total_pages
            for i in range(min(3, total_pages), total_pages):
                t = pdf.pages[i].extract_text() or ""
                if re.search(r'(?m)^Ответы\s*$|^Ответы и критерии|^Система оценивания|^Критерии оценивания', t):
                    cut_page = i
                    print(f"   📍 cut_page: стр. {i+1}")
                    break
            print(f"   📄 страниц: {total_pages}, обрабатываем: {cut_page}")

        pages_imgs = []
        with pdfplumber.open(tmp) as pdf:
            for i in range(cut_page):
                ppath = f"{IMG_DIR}/{base}_p{i+1}.jpg"
                if not os.path.exists(ppath):
                    try:
                        img = pdf.pages[i].to_image(resolution=120)
                        pil = img.original
                        if pil.mode != 'RGB':
                            pil = pil.convert('RGB')
                        pil.save(ppath, format="JPEG", quality=75)
                    except Exception as e:
                        print(f"   ⚠️ render p{i+1}: {e}")
                        continue
                pages_imgs.append((i, ppath))
        print(f"   🖼 отрендерено: {len(pages_imgs)}")

        tasks = []
        seen_texts = set()
        for i, ppath in pages_imgs:
            with open(ppath, "rb") as f:
                data_uri = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
            data = None
            for attempt in range(2):
                try:
                    data, _ = ask_vision(data_uri)
                    break
                except Exception as e:
                    print(f"   ⚠️ vision p{i+1} (попытка {attempt+1}): {e}")
                    time.sleep(2)
            if not data:
                continue
            rel = f"{IMG_DIR}/{base}_p{i+1}.jpg"
            for b in data.get("blocks", []):
                txt = (b.get("text") or "").strip()
                if len(txt) < 20:
                    continue
                ans = (b.get("answer") or "").strip()
                num = b.get("num")
                try:
                    num = int(num) if num is not None else None
                except:
                    num = None
                sig = txt[:100]
                if sig in seen_texts:
                    continue
                seen_texts.add(sig)
                if num is None and tasks:
                    tasks[-1]["task_text"] += "\n" + txt
                    if rel not in tasks[-1]["all_images"]:
                        tasks[-1]["all_images"].append(rel)
                    if ans:
                        tasks[-1]["answer"] = ans
                else:
                    tasks.append({
                        "id": f"vpr_{subj}_{grade}_{level}{year}_p{i+1}_n{len(tasks)}",
                        "task_text": txt,
                        "answer": ans or "---",
                        "image": "",
                        "all_images": [rel],
                        "audio": "",
                        "all_audios": [],
                        "topic": f"vpr_{grade}_klass",
                    })
        results.setdefault(key, []).extend(tasks)
        print(f"   ✅ ИТОГО: {len(tasks)} задач")
    except Exception as e:
        print(f"⚠️ {fname}: {e}")
    time.sleep(0.2)

print("\n=== СОХРАНЕНИЕ ===")
total = 0
for key, tasks in results.items():
    if tasks:
        with open(f"questions/vpr_{key}.json", "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"💾 vpr_{key}: {len(tasks)}")
        total += len(tasks)
print(f"🎉 ВСЕГО: {total} задач ВПР!")
