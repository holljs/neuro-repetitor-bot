import re

with open('parse_sdamgia.py', 'r', encoding='utf-8') as f:
    code = f.read()

# БЫЛО: удаляли minor целиком
# for bad in body.find_all(class_=re.compile(r"solution|minor")):
#     bad.decompose()

# СТАЛО: удаляем ТОЛЬКО solution, а minor чистим от мусора
old_pattern = r'for bad in body\.find_all\(class_=re\.compile\(r"solution\|minor"\)\):\s+bad\.decompose\(\)'
new_code = '''# Удаляем решения (solution) целиком
        for bad in body.find_all(class_=re.compile(r"solution")):
            bad.decompose()
        # Чистим minor от мусорных фраз, но оставляем формулировки заданий
        for minor in body.find_all(class_=re.compile(r"minor")):
            for p in minor.find_all("p"):
                txt = p.get_text(strip=True)
                if any(junk in txt.lower() for junk in ["решения заданий", "самостоятельно", "критерии оценивания", "баллы"]):
                    p.decompose()'''

code = re.sub(old_pattern, new_code, code)

with open('parse_sdamgia.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("✅ Парсер исправлен: minor блоки теперь чистятся, а не удаляются")
