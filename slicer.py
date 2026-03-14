import fitz  # PyMuPDF
import os
from pathlib import Path

def slice_pdf(pdf_path, start_page, end_page, topic_folder):
    """
    pdf_path: путь к файлу math_oge.pdf
    start_page: с какой страницы начать (как в учебнике)
    end_page: какой страницей закончить
    topic_folder: название папки темы (например, topic_02_calc)
    """
    output_dir = Path(f"questions/images_oge_math/{topic_folder}")
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    
    # В PDF индексация начинается с 0, поэтому вычитаем 1
    # Если в твоем PDF страницы смещены относительно нумерации учебника, 
    # подправь это число (например, start_page + 5)
    for page_num in range(start_page - 1, end_page):
        page = doc.load_page(page_num)
        
        # Высокое качество (зум 2.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        
        image_name = f"page_{page_num + 1}.jpg"
        pix.save(output_dir / image_name)
        print(f"✅ Сохранена страница {page_num + 1} в {topic_folder}")

    doc.close()

if __name__ == "__main__":
    # ПРИМЕР ЗАПУСКА: Режем § 2. Вычисления (стр. 31-47)
    # slice_pdf("math_oge.pdf", 31, 47, "topic_02_calc")
    
    print("🚀 Нарезчик готов. Раскомментируй нужную строку в коде для запуска!")
