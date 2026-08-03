import sys
import json
import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_fipi(proj_id, subject_code, max_pages=10):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://oge.fipi.ru",
        "Referer": f"https://oge.fipi.ru/bank/index.php?proj={proj_id}"
    })

    print(f"🚀 Парсинг ФИПИ (Регулярный поиск по /docs/ и картинкам): {subject_code}")

    try:
        session.get(f"https://oge.fipi.ru/bank/index.php?proj={proj_id}", verify=False, timeout=15)
        print("✅ Сессия получена!")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return

    parsed_tasks = []
    questions_url = "https://oge.fipi.ru/bank/questions.php"

    for page in range(1, max_pages + 1):
        print(f"⏳ Скачиваем страницу {page} из {max_pages}...")

        payload = {
            "search": "1",
            "pagesize": "10",
            "proj": proj_id,
            "page": str(page)
        }

        try:
            resp = session.post(questions_url, data=payload, verify=False, timeout=15)
            if resp.status_code != 200:
                continue

            resp.encoding = 'windows-1251'
            soup = BeautifulSoup(resp.text, 'html.parser')

            blocks = soup.find_all('div', class_='qblock')
            if not blocks:
                blocks = soup.find_all('form', id=re.compile(r'^checkform'))
            if not blocks:
                blocks = soup.find_all('table', class_='qblock')

            if not blocks:
                print(f"📭 На странице {page} задачи не найдены.")
                break

            for idx, block in enumerate(blocks):
                block_id = block.get('id', '') or block.get('name', '')
                task_id = re.sub(r'\D', '', block_id)
                if not task_id:
                    num_match = re.search(r'Номер:\s*([A-Z0-9]+)', block.get_text(), re.IGNORECASE)
                    task_id = num_match.group(1) if num_match else f"{page}_{idx}"

                lines = [line.strip() for line in block.get_text(separator="\n").split("\n") if line.strip()]
                clean_lines = []
                for line in lines:
                    if not any(x in line for x in ['Номер:', 'ОТВЕТИТЬ', 'НЕ РЕШЕНО', 'ПОДБОР ЗАДАНИЙ', 'Кол-во заданий']):
                        clean_lines.append(line)

                full_text = "\n".join(clean_lines).strip()
                if len(full_text) < 10:
                    continue

                # 🎯 ПРЯМОЙ ПОИСК ВСЕХ КАРТИНОК В СЫРОМ HTML КАРТОЧКИ
                raw_html = str(block)
                imgs = []

                # Ищем всё, что содержит .jpg, .jpeg, .png, .gif или пути /docs/
                found_urls = re.findall(r'(?:https?://oge\.fipi\.ru)?(/[^\s\'"<>]+\.(?:jpg|jpeg|png|gif))', raw_html, re.IGNORECASE)
                found_docs = re.findall(r'(/docs/[^\s\'"<>]+\.[a-zA-Z0-9]+)', raw_html, re.IGNORECASE)

                for path in found_urls + found_docs:
                    if any(icon in path.lower() for icon in ['icon', 'button', 'arrow', 'btn', 'system', 'check.png', 'cross.png']):
                        continue
                    
                    full_url = path if path.startswith('http') else f"https://oge.fipi.ru{path}"
                    if full_url not in imgs:
                        imgs.append(full_url)

                task_obj = {
                    "id": f"fipi_{task_id}",
                    "task_text": full_text,
                    "image": imgs[0] if imgs else "",
                    "all_images": imgs,
                    "answer": "---",
                    "topic": subject_code
                }

                if not any(t['id'] == task_obj['id'] for t in parsed_tasks):
                    parsed_tasks.append(task_obj)

            print(f"✅ Страница {page} готова! Собрано: {len(parsed_tasks)}")
            time.sleep(1.0)

        except Exception as e:
            print(f"💥 Ошибка на странице {page}: {e}")

    output_path = f"questions/{subject_code}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed_tasks, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 СБОР ЗАВЕРШЕН! Сохранено {len(parsed_tasks)} задач в файл: {output_path}")

if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else "0E1FA4229923A5CE4FC368155127ED90"
    code = sys.argv[2] if len(sys.argv) > 2 else "oge_biology"
    pages = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    parse_fipi(proj, code, pages)
