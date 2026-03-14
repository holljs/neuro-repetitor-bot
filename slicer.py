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
slice_pdf("math_oge.pdf", 31, 47, "topic_02_calc")

# § 3. Единицы измерения величин (стр. 50-60)
slice_pdf("math_oge.pdf", 50, 60, "topic_03_units")

# § 4. Уравнения и неравенства (стр. 61-71)
slice_pdf("math_oge.pdf", 61, 71, "topic_04_eq_ineq")

# § 5. Координатная прямая (стр. 72-89)
slice_pdf("math_oge.pdf", 72, 89, "topic_05_line")

# § 6. Графики и диаграммы (стр. 90-106)
slice_pdf("math_oge.pdf", 90, 106, "topic_06_charts")

# § 7. Графики функций (стр. 107-126)
slice_pdf("math_oge.pdf", 107, 126, "topic_07_functions")

# § 8. Алгебраические выражения (стр. 127-133)
slice_pdf("math_oge.pdf", 127, 133, "topic_08_expr")

# § 9. Выражение величины из формулы (стр. 134-142)
slice_pdf("math_oge.pdf", 134, 142, "topic_09_formulas")

# § 10. Последовательности (Прогрессии) (стр. 143-148)
slice_pdf("math_oge.pdf", 143, 148, "topic_10_seq")

# § 11. Текстовые задачи (стр. 149-157)
slice_pdf("math_oge.pdf", 149, 157, "topic_11_text")

# § 12. Текстовые задачи (сложные) (стр. 158-167)
slice_pdf("math_oge.pdf", 158, 167, "topic_12_hard_text")

# § 13. Теория вероятностей (стр. 168-173)
slice_pdf("math_oge.pdf", 168, 173, "topic_13_prob")


# --- ЧАСТЬ 2. ГЕОМЕТРИЯ ---

# § 1. Подсчёт углов (Треугольники, окружности) (стр. 174-189)
slice_pdf("math_oge.pdf", 174, 189, "topic_geom_01_angles")

# § 2. Площади фигур (стр. 190-205)
slice_pdf("math_oge.pdf", 190, 205, "topic_geom_02_areas")

# § 3. Реальная планиметрия (стр. 206-214)
slice_pdf("math_oge.pdf", 206, 214, "topic_geom_03_pract")

# § 4. Выбор верных утверждений (стр. 215-228)
slice_pdf("math_oge.pdf", 215, 228, "topic_geom_04_logic")
    
    print("🚀 Нарезчик готов. Раскомментируй нужную строку в коде для запуска!")
