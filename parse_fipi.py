import sys
import json
import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 🔥 Карты через СЛОВАРИ — ошибка "unequal length" невозможна
SUB_DICT = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ',
    'o': 'ₒ', 'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ', 'v': 'ᵥ', 'x': 'ₓ'
}
SUP_DICT = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'i': 'ⁱ', 'n': 'ⁿ', 't': 'ᵗ', 'x': 'ˣ'
}
SUB_MAP = str.maketrans(SUB_DICT)
SUP_MAP = str.maketrans(SUP_DICT)


def compact_lines(lines):
    """Склеивает 'рваные' обрывки формул в нормальные строки."""
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if out:
            prev = out[-1]
            # "4" + "7" -> "47" (без пробела)
            if re.fullmatch(r'\d+', line) and re.search(r'\d$', prev):
                out[-1] = prev + line
                continue
            is_option = re.match(r'^\d+[\.\)]', line)
            is_marker = line.startswith(('📖', '❓', '🎧'))
            both_long = len(line) > 20 and len(prev) > 20
            prev_ends = re.search(r'[.!?]$', prev)
            if not is_option and not is_marker and not (both_long and prev_ends):
                out[-1] = prev + ' ' + line
                continue
        out.append(line)
    return out


def parse_fipi(proj_id, subject_code, max_pages=175):
    base_domain = "https://oge.fipi.ru" if subject_code.startswith("oge_") or "oge" in subject_code.lower() else "https://ege.fipi.ru"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": base_domain,
        "Referer": f"{base_domain}/bank/index.php?proj={proj_id}"
    })

    print(f"🚀 Запуск умного парсинга ФИПИ [{subject_code}] | Домен: {base_domain} | Проект: {proj_id}")
    try:
        session.get(f"{base_domain}/bank/index.php?proj={proj_id}", verify=False, timeout=15)
        print("✅ Сессия ФИПИ успешно получена!")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return

    parsed_tasks = []
    questions_url = f"{base_domain}/bank/questions.php"

    for page in range(1, max_pages + 1):
        print(f"⏳ Скачиваем страницу {page} из {max_pages}...")
        payload = {"search": "1", "pagesize": "10", "proj": proj_id, "page": str(page)}
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
            main_container = soup.find('div', id='questions_container') or soup
            current_passage_text = ""

            elements = main_container.find_all(['div', 'form', 'p', 'td'])
            for el in elements:
                el_text = el.get_text().strip()
                if any(start_kw in el_text for start_kw in ["Прочитайте текст", "Прочитайте приведенный фрагмент", "Прочитайте стихотворение"]):
                    if len(el_text) > 50:
                        current_passage_text = el_text

                is_qblock = ('qblock' in el.get('class', [])) or el.name == 'form' or ('checkform' in el.get('id', ''))
                if not is_qblock or not el.get('id'):
                    continue

                block = el
                block_id = block.get('id', '') or ''
                task_num = re.sub(r'checkform', '', block_id, flags=re.I)
                raw_html = str(block)

                # 🎵 АУДИО
                audios = []
                mp3_in_script = re.findall(r"ShowPictureQ2WH\s*\(\s*['\"]([^'\"]+\.mp3)['\"]", raw_html, re.IGNORECASE)
                mp3_in_html = re.findall(r'(?:https?://[^\s\'"<>]+\.fipi\.ru)?(/[^\s\'"<>]+\.(?:mp3|wav|ogg|m4a))', raw_html, re.IGNORECASE)
                for path in mp3_in_script + mp3_in_html:
                    full_url = path if path.startswith('http') else f"{base_domain}/{path.lstrip('/')}"
                    if full_url not in audios:
                        audios.append(full_url)

                # 🖼 КАРТИНКИ
                imgs = []
                found_srcs = re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|gif))["\']', raw_html, re.IGNORECASE)
                found_docs = re.findall(r'(?:https?://[^\s\'"<>]+\.fipi\.ru)?(/[^\s\'"<>]+\.(?:jpg|jpeg|png|gif))', raw_html, re.IGNORECASE)
                for path in found_srcs + found_docs:
                    if any(icon in path.lower() for icon in ['icon_', 'button', 'arrow', 'btn_', 'system_', 'check.png', 'cross.png']):
                        continue
                    full_url = path if path.startswith('http') else f"{base_domain}/{path.lstrip('/')}"
                    if full_url not in imgs and not any(ext in full_url.lower() for ext in ['.mp3', '.wav', '.ogg']):
                        imgs.append(full_url)

                # 🧹 ГЛУБОКАЯ ОЧИСТКА И ПРЕВРАЩЕНИЕ ФОРМУЛ В LATEX
                clean_block = BeautifulSoup(raw_html, 'html.parser')

                # 1. Оригинальный LaTeX из MathJax / MathML alt-атрибутов (сразу в $...$)
                for math_tag in clean_block.find_all(['mjx-container', 'math']):
                    latex_attr = math_tag.get('data-semantic-content') or math_tag.get('alt') or math_tag.get('aria-label')
                    if latex_attr:
                        math_tag.replace_with(f" ${latex_attr}$ ")

                # 2. ВЕКТОРЫ (mover)
                for mover in clean_block.find_all(['mover']):
                    vec_base = mover.get_text().strip()
                    if vec_base:
                        mover.replace_with(f" $\\vec{{{vec_base}}}$ ")

                # 3. ИНДЕКСЫ + СТЕПЕНИ (msubsup)
                for msubsup in clean_block.find_all(['msubsup']):
                    parts = msubsup.find_all(['mn', 'mi', 'mo', 'span'])
                    if len(parts) >= 3:
                        subsup_base = parts[0].get_text().strip()
                        sub_part = parts[1].get_text().strip()
                        sup_part = parts[2].get_text().strip()
                        msubsup.replace_with(f" ${subsup_base}_{{{sub_part}}}^{{{sup_part}}}$ ")

                # 4. ДРОБИ (mfrac)
                for frac in clean_block.find_all(['mfrac', 'mjx-frac']):
                    num = frac.find(['mn', 'mi', 'mjx-num', 'span'])
                    den_tags = frac.find_all(['mn', 'mi', 'mjx-den', 'span'])
                    den = den_tags[-1] if den_tags else None
                    if num and den:
                        frac.replace_with(f" $\\frac{{{num.get_text().strip()}}}{{{den.get_text().strip()}}}$ ")

                # 5. КОРНИ (msqrt, mroot)
                for sqrt in clean_block.find_all(['msqrt']):
                    sqrt_text = sqrt.get_text().strip()
                    if sqrt_text:
                        sqrt.replace_with(f" $\\sqrt{{{sqrt_text}}}$ ")
                for mroot in clean_block.find_all(['mroot']):
                    deg_and_base = mroot.find_all(['mn', 'mi', 'span'])
                    if len(deg_and_base) >= 2:
                        mroot.replace_with(f" $\\sqrt[{deg_and_base[1].get_text().strip()}]{{{deg_and_base[0].get_text().strip()}}}$ ")
                    else:
                        mroot.replace_with(f" $\\sqrt{{{mroot.get_text().strip()}}}$ ")

                # 6. СТЕПЕНИ/ИНДЕКСЫ: юникод для простых (химия), LaTeX для сложных
                for sup in clean_block.find_all(['sup', 'msup']):
                    inner = sup.get_text().strip()
                    if not inner:
                        sup.decompose()
                        continue
                    if all(c in SUP_DICT for c in inner):
                        sup.replace_with(inner.translate(SUP_MAP))
                    else:
                        sup.replace_with(f"^{{{inner}}}")
                for sub in clean_block.find_all(['sub', 'msub']):
                    inner = sub.get_text().strip()
                    if not inner:
                        sub.decompose()
                        continue
                    if all(c in SUB_DICT for c in inner):
                        sub.replace_with(inner.translate(SUB_MAP))
                    else:
                        sub.replace_with(f"_{{{inner}}}")

                # 🔥 Остатки <math> схлопываем в ОДНУ строку (конец "столбикам")
                for math in clean_block.find_all('math'):
                    math.replace_with(' ' + ' '.join(math.get_text().split()) + ' ')

                # 7. Мусор управления
                for s in clean_block.find_all(['select', 'input', 'button', 'script', 'style']):
                    s.decompose()
                for hidden in clean_block.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
                    hidden.decompose()

                block_text = clean_block.get_text(separator="\n")

                # 8. Нормализация LaTeX
                block_text = re.sub(r'([a-zA-Zа-яА-Я0-9])\s*\^', r'\1^', block_text)
                block_text = re.sub(r'([a-zA-Zа-яА-Я0-9])\s*\_', r'\1_', block_text)
                # голые _{...}/^{...} оборачиваем в $...$
                block_text = re.sub(
                    r'(?<!\$)([A-Za-zА-Яа-яЁё0-9\)\]](?:\s*[_^]\{[^}]*\})+)(?!\$)',
                    r' $\1$ ',
                    block_text
                )
                # убираем переносы ВНУТРИ $...$
                block_text = re.sub(r'\$([^$]+)\$', lambda m: '$' + ' '.join(m.group(1).split()) + '$', block_text)
                block_text = re.sub(r'\$\s*\$', '', block_text)

                # 9. Фильтр мусорных строк + умная склейка
                lines = [l.strip() for l in block_text.split("\n") if l.strip()]
                clean_lines = [l for l in lines if not any(x in l for x in [
                    'Номер:', 'ОТВЕТИТЬ', 'НЕ РЕШЕНО', 'ПОДБОР ЗАДАНИЙ',
                    'Кол-во заданий', 'Статус задания', 'ИЗМЕНИТЬ СТАТУС',
                    'Добавить в вариант', 'Вопросов в варианте'
                ])]
                task_text_only = "\n".join(compact_lines(clean_lines)).strip()

                if current_passage_text and current_passage_text not in task_text_only:
                    full_text = f"📖 Фрагмент/Текст:\n{current_passage_text}\n\n❓ Задание:\n{task_text_only}"
                else:
                    full_text = task_text_only

                if len(full_text) < 10 and not imgs:
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
            time.sleep(0.2)
        except Exception as e:
            print(f"💥 Ошибка на странице {page}: {e}")

    output_path = f"questions/{subject_code}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parsed_tasks, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 СБОР ЗАВЕРШЕН! Сохранено {len(parsed_tasks)} задач в файл: {output_path}")


if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else "DE0E276E497AB3784C3FC4CC20248DC0"
    code = sys.argv[2] if len(sys.argv) > 2 else "oge_math"
    pages = int(sys.argv[3]) if len(sys.argv) > 3 else 175
    parse_fipi(proj, code, pages)
