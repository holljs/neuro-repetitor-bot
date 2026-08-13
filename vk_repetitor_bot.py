import os
import sqlite3
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import random
import time
from dotenv import load_dotenv

# Загружаем переменные
load_dotenv()
VK_TOKEN = os.getenv("VK_REPETITOR_TOKEN")
ADMIN_VK_ID = 233876992  # Твой ID
GROUP_ID = 235924452     # ⚠️ ID ТВОЕЙ ГРУППЫ РЕПЕТИТОРА!

# Подключаемся к ВК как ГРУППА
vk_session = vk_api.VkApi(token=VK_TOKEN)
longpoll = VkBotLongPoll(vk_session, GROUP_ID)
vk = vk_session.get_api()

print("🎓 VK-бот (Швейцар + Админка Репетитора) запущен...")

# --- БАЗА ДАННЫХ (С АВТОМИГРАЦИЕЙ) ---
DB_PATH = "vk_users.db"
BONUS_AMOUNT = 6

def init_db():
    """Создает таблицу и добавляет колонку has_bonus, если её нет"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        credits INTEGER DEFAULT 0,
        has_bonus INTEGER DEFAULT 0,
        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    try:
        # Пытаемся добавить колонку для старых баз
        cursor.execute("ALTER TABLE users ADD COLUMN has_bonus INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Колонка уже есть
    conn.commit()
    conn.close()

init_db() # Запускаем при старте бота

def get_balance(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT credits FROM users WHERE user_id=?", (str(user_id),))
        res = cursor.fetchone()
        return res[0] if res else None

def add_credits(user_id, amount):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT credits FROM users WHERE user_id=?", (str(user_id),))
        if cursor.fetchone():
            cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, str(user_id)))
        else:
            cursor.execute("INSERT INTO users (user_id, credits, has_bonus) VALUES (?, ?, 0)", (str(user_id), amount))
        conn.commit()

def count_users():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

def get_all_users():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return [row[0] for row in cursor.fetchall()]

# --- СИСТЕМА БОНУСОВ (Теперь мгновенная через SQLite!) ---
def check_and_give_bonus(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT has_bonus FROM users WHERE user_id=?", (str(user_id),))
        res = cursor.fetchone()
        
        if res and res[0] == 1:
            return False # Уже получал бонус
            
        # Начисляем бонус и ставим флаг 1
        if res:
            cursor.execute("UPDATE users SET credits = credits + ?, has_bonus = 1 WHERE user_id=?", (BONUS_AMOUNT, str(user_id)))
        else:
            cursor.execute("INSERT INTO users (user_id, credits, has_bonus) VALUES (?, ?, 1)", (str(user_id), BONUS_AMOUNT))
        conn.commit()
        return True

# --- ФУНКЦИИ ВК ---
def send_message(user_id, message, keyboard=None, attachment=None):
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": random.getrandbits(64)
    }
    if keyboard: 
        try: params["keyboard"] = keyboard.get_keyboard()
        except AttributeError: params["keyboard"] = keyboard
    if attachment:
        params["attachment"] = attachment

    try: 
        vk.messages.send(**params)
    except Exception as e: 
        # 901 = юзер запретил сообщения от группы, 900 = юзер удалился
        if "901" in str(e) or "900" in str(e) or "936" in str(e):
            pass # Молча игнорируем заблокировавших нас
        else:
            print(f"Ошибка отправки {user_id}: {e}")

def get_app_keyboard():
    keyboard = VkKeyboard(inline=True)
    keyboard.add_openlink_button(
        label="🧠 Открыть Нейро-Репетитор",
        link="https://vk.com/app51800000" # ⚠️ ЗАМЕНИ НА ID ТВОЕГО ПРИЛОЖЕНИЯ
    )
    return keyboard

# --- ГЛАВНЫЙ ЦИКЛ БОТА ---
for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        # 🔥 ПРАВИЛЬНОЕ ОБРАЩЕНИЕ К СООБЩЕНИЮ ДЛЯ ГРУПП
        message = event.obj.message 
        user_id = message.from_id
        original_text = message.text.strip()
        text = original_text.lower()

        # Игнорируем сообщения от других сообществ (у них отрицательный ID)
        if user_id < 0:
            continue

        # ---------------- СЕКРЕТНАЯ АДМИНКА ----------------
        if user_id == ADMIN_VK_ID:
            
            if text.startswith("выдать"):
                try:
                    parts = text.split()
                    target_id = int(parts[1])
                    amount = int(parts[2])
                    add_credits(target_id, amount)
                    send_message(user_id, f"✅ Успешно!\nУченику @id{target_id} начислено {amount} кр.\nЕго баланс: {get_balance(target_id)} кр.")
                except:
                    send_message(user_id, "❌ Формат: выдать 12345678 50")
                continue
                
            elif text.startswith("проверить") or text.startswith("баланс"):
                try:
                    target_id = int(text.split()[1])
                    balance = get_balance(target_id)
                    if balance is None:
                        send_message(user_id, f"❌ Ученик @id{target_id} не найден в базе!")
                    else:
                        send_message(user_id, f"🔍 Баланс ученика @id{target_id}:\n💰 Кредиты: {balance} кр.")
                except:
                    send_message(user_id, "❌ Формат: проверить 12345678")
                continue
                
            elif text in ["стата", "статистика"]:
                try:
                    total_users = count_users()
                    send_message(user_id, f"📊 СТАТИСТИКА РЕПЕТИТОРА:\n\n👥 Всего учеников в базе: {total_users} чел.")
                except Exception as e:
                    send_message(user_id, f"❌ Ошибка: {e}")
                continue
                
            elif text.startswith("рассылка"):
                try:
                    # 🔥 УМНОЕ РАЗДЕЛЕНИЕ: не съест первую букву текста!
                    parts = original_text.split(maxsplit=1)
                    broadcast_text = parts[1].strip() if len(parts) > 1 else ""
                    
                    attachments = []
                    if message.attachments:
                        for att in message.attachments:
                            if att['type'] == 'photo':
                                photo = att['photo']
                                attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
                    att_string = ",".join(attachments) if attachments else None

                    if not broadcast_text and not att_string:
                        send_message(user_id, "❌ Пустая рассылка! Напиши текст или прикрепи фото.")
                        continue

                    users = get_all_users()
                    if not users:
                        send_message(user_id, "❌ База данных пуста!")
                        continue

                    success_count, error_count = 0, 0
                    send_message(user_id, f"⏳ Начинаю рассылку по базе: {len(users)} чел.")
                    
                    for user_db_id in users:
                        send_message(int(user_db_id), broadcast_text, attachment=att_string)
                        success_count += 1
                        time.sleep(0.07) # Чуть быстрее, лимит ВК 20/сек
                    
                    send_message(user_id, f"✅ Рассылка завершена!\n\n📈 Успешно: {success_count}\n❌ Ошибок: {error_count}")
                except Exception as e:
                    send_message(user_id, f"❌ Критическая ошибка рассылки: {e}")
                continue

        # ---------------- ЛОГИКА ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ ----------------
        
        is_new_subscriber = check_and_give_bonus(user_id)
        
        if is_new_subscriber:
            msg = (
                f"🎉 Отлично! Вы разрешили сообщения, и мы начислили вам {BONUS_AMOUNT} бесплатных кредитов!\n\n"
                "🤖 Вся подготовка к ОГЭ и ЕГЭ, проверка задач и подробные разборы ошибок с ИИ происходят внутри нашего мини-приложения 👇\n\n"
                "Если у вас есть вопросы по работе сервиса — пишите прямо сюда, мы всегда на связи!"
            )
        else:
            msg = (
                "👋 Привет! Добро пожаловать в поддержку Нейро-Репетитора!\n\n"
                "🤖 Вся подготовка к ОГЭ и ЕГЭ, проверка задач и подробные разборы ошибок с ИИ происходят внутри нашего мини-приложения 👇\n\n"
                "Если вы нашли ошибку в задаче или у вас есть вопрос — пишите сюда, администраторы ответят в ближайшее время!"
            )
            
        send_message(user_id, msg, get_app_keyboard())
