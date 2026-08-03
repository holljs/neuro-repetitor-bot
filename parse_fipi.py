import sys
import json
import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_fipi(proj_id, subject_code, max_pages=175):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://oge.fipi.ru",
        "Referer": f"https://oge.fipi.ru/bank/index.php?proj={proj_id}"
    })

    print(f"🚀 Запуск парсинга ФИПИ [{subject_code}] | Проект: {proj_id}")

    try:
        session.get(f"https://oge.fipi.ru/bank/index.php?proj={proj_id}", verify=False, timeout=15)
        print("✅ Сессия ФИПИ успешно получена!")
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
                print(f"⚠️ Ошибка ответа сервера: status {resp.status_code}")
                continue

            try:
                html_text = resp.content.decode('utf-8')
            except UnicodeDecodeError:
                html_text = resp.content.decode('windows-1251', errors='ignore')

            soup = BeautifulSoup(html_text, 'html.parser')

            forms = soup.find_all('form', id=re.compile(r'^checkform', re.I))
            if not forms:
                forms = soup.find_all('div', class_=re.compile(r'qblock', re.I))
            if not forms:
                forms = soup.find_all('td', class_='cell_0')

            if not forms:
                print(f"📭 На странице {page} больше нет задач.")
                break

            for idx, block in enumerate(forms):
                block_id = block.get('id', '') or ''
                task_num = re.sub(r'checkform', '', block_id, flags=re.I)
                
                if not task_num:
                    num_match = re.search(r'Номер:\s*([A-Z0-9]+)', block.get_text(), re.IGNORECASE)
                    task_num = num_match.group(1) if num_match else f"p{page}_{idx+1}"

                raw_html = str(block)

                # 🎵 1. ПОИСК АУДИО (включая скрипты ShowPictureQ2WH)
                audios = []
                mp3_in_script = re.findall(r"ShowPictureQ2WH\s*\(\s*['\"]([^'\"]+\.mp3)['\"]", raw_html, re.IGNORECASE)
                mp3_in_html = re.findall(r'(?:https?://oge\.fipi\.ru)?(/[^\s\'"<>]+\.(?:mp3|wav|ogg|m4a))', raw_html, re.IGNORECASE)

                for path in mp3_in_script + mp3_in_html:
                    full_url = path if path.startswith('http') else f"https://oge.fipi.ru/{path.lstrip('/')}"
                    if full_url not in audios:
                        audios.append(full_url)

                # 🖼 2. ПОИСК КАРТИНОК И СХЕМ
                imgs = []
                found_srcs = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|gif))["\']', raw_html, re.IGNORECASE)
                found_docs = re.findall(r'(?:https?://oge\.fipi\.ru)?(/[^\s\'"<>]+\.(?:jpg|jpeg|png|gif))', raw_html, re.IGNORECASE)

                for path in found_srcs + found_docs:
                    if any(icon in path.lower() for icon in ['icon', 'button', 'arrow', 'btn', 'system', 'check.png', 'cross.png', 'simg1_']):
                        continue
                    
                    full_url = path if path.startswith('http') else f"https://oge.fipi.ru/{path.lstrip('/')}"
                    if full_url not in imgs and not any(ext in full_url.lower() for ext in ['.mp3', '.wav', '.ogg']):
                        imgs.append(full_url)

                # 🧹 3. ОЧИСТКА ТЕКСТА
                clean_block = BeautifulSoup(raw_html, 'html.parser')
                for s in clean_block.find_all(['select', 'input', 'button', 'script']):
                    s.decompose()

                block_text = clean_block.get_text(separator="\n")
                lines = [line.strip() for line in block_text.split("\n") if line.strip()]
                clean_lines = []
                for line in lines:
                    if not any(x in line for x in ['Номер:', 'ОТВЕТИТЬ', 'НЕ РЕШЕНО', 'ПОДБОР ЗАДАНИЙ', 'Кол-во заданий', 'Статус задания', 'ИЗМЕНИТЬ СТАТУС']):
                        clean_lines.append(line)

                full_text = "\n".join(clean_lines).strip()
                if len(full_text) < 15:
                    continue

                task_obj = {
                    "id": f"fipi_{task_num}",
                    "task_text": full_text,
                    "image": imgs[0] if imgs else "",
                    "all_images": imgs,
                    "audio": audios[0] if audios else "",
                    "all_audios": audios,
                    "answer": "---",
                    "topic": subject_code
                }

                if not any(t['id'] == task_obj['id'] for t in parsed_tasks):
                    parsed_tasks.append(task_obj)

            print(f"✅ Страница {page} готова! Всего собрано: {len(parsed_tasks)} задач.")
            time.sleep(0.3)

        except Exception as e:
            print(f"💥 Ошибка на странице {page}: {e}")

    output_path = f"questions/{subject_code}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed_tasks, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 СБОР ЗАВЕРШЕН! Сохранено {len(parsed_tasks)} задач в файл: {output_path}")

if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else "74676951F093A0754D74F2D6E7955F06"
    code = sys.argv[2] if len(sys.argv) > 2 else "oge_informatics"
    pages = int(sys.argv[3]) if len(sys.argv) > 3 else 175

    parse_fipi(proj, code, pages)
