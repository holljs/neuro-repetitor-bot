import PyPDF2

def extract_answers():
    pdf_path = "math_oge.pdf"
    output_txt = "answers_raw.txt"
    
    # ВНИМАНИЕ: Укажите здесь реальные номера страниц с ответами из вашего PDF!
    # Например, если ответы идут с 230 по 245 страницу:
    start_page = 229
    end_page = 238 
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            with open(output_txt, 'w', encoding='utf-8') as out:
                # В PyPDF2 нумерация страниц начинается с 0, поэтому делаем -1
                for i in range(start_page - 1, end_page):
                    text = reader.pages[i].extract_text()
                    out.write(text + "\n")
        print(f"✅ Текст ответов успешно сохранен в файл {output_txt}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    extract_answers()
