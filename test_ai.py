import os
import replicate
import base64
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

# Проверяем, подгрузился ли токен
api_token = os.getenv("REPLICATE_API_TOKEN")

if not api_token:
    print("❌ Ошибка: Токен не найден в .env! Проверь файл .env.")
else:
    # Явно передаем токен в переменную окружения, которую ждет библиотека replicate
    os.environ["REPLICATE_API_TOKEN"] = api_token

PAGE_PATH = "questions/images_oge_math/topic_01_models/page_20.jpg"

def test_smart_crop():
    if not os.path.exists(PAGE_PATH):
        print(f"❌ Файл не найден: {PAGE_PATH}")
        return

    with open(PAGE_PATH, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")

    model = "google/gemini-3-flash"
    
    print(f"⏳ Запрос к {model} (токен подгружен)...")
    try:
        output = replicate.run(
            model,
            input={
                "image": f"data:image/jpeg;base64,{img_data}",
                "prompt": "Найди задачу номер 1. Верни JSON: {'box_2d': [ymin, xmin, ymax, xmax]}"
            }
        )
        print("🤖 Ответ ИИ:", "".join(output))
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    test_smart_crop()
