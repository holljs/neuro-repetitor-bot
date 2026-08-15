import json, glob, os, concurrent.futures as cf, urllib.request, urllib.error

os.makedirs('questions/quarantine', exist_ok=True)
files = sorted(glob.glob('questions/vpr_*.json'))
urls = set()
for f in files:
    for t in json.load(open(f, encoding='utf-8')):
        for u in (t.get('all_images') or ([t['image']] if t.get('image') else [])):
            if u: urls.add(str(u))

log = open('vpr_image_report.txt', 'w', encoding='utf-8')
log.write(f"Уникальных URL: {len(urls)}\n"); log.flush()

def check(u):
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(u, method=method, headers={'User-Agent': 'Mozilla/5.0'})
            r = urllib.request.urlopen(req, timeout=5)
            ok = r.status < 400
            r.close()
            return (u, ok)
        except urllib.error.HTTPError as e:
            if e.code in (403, 405): continue
            return (u, False)
        except Exception:
            return (u, False)
    return (u, False)

dead = set(); done = 0
with cf.ThreadPoolExecutor(60) as ex:
    for u, ok in ex.map(check, list(urls)):
        done += 1
        if not ok: dead.add(u)
        if done % 1000 == 0:
            log.write(f"прогресс: {done}/{len(urls)}, мёртвых: {len(dead)}\n"); log.flush()

log.write(f"\n❌ Мёртвых URL: {len(dead)} из {len(urls)}\n\n")

total_q = 0
for f in files:
    tasks = json.load(open(f, encoding='utf-8'))
    good, bad = [], []
    for t in tasks:
        imgs = [str(u) for u in (t.get('all_images') or ([t['image']] if t.get('image') else []))]
        (bad if any(u in dead for u in imgs) else good).append(t)
    if bad:
        json.dump(good, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        json.dump(bad, open('questions/quarantine/' + os.path.basename(f), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        total_q += len(bad)
        log.write(f"📦 {os.path.basename(f)}: в карантин {len(bad)}, осталось {len(good)}\n")

log.write(f"\nВСЕГО в карантине: {total_q}\nDONE ✅\n")
log.close()
print("DONE")
