import os
import sqlite3
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import random
import time
from dotenv import load_dotenv

# Загружаем переменные (Убедись, что VK_TOKEN есть в .env)
load_dotenv()
VK_TOKEN = os.getenv("VK_TOKEN")
ADMIN_VK_ID = 233876992  # Твой ID для админских команд

# Подключаемся к ВК
vk_session = vk_api.VkApi(token=VK_TOKEN)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()

print("🎓 VK-бот (Швейцар + Админка Репетитора) запущен...")

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
DB_PATH = "vk_users.db"

def get_balance(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (str(user_id),))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def add_credits(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id=?", (str(user_id),))
    if cursor.fetchone():
        cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, str(user_id)))
    else:
        # Если юзер еще ни разу не открывал апп, но уже написал боту
        cursor.execute("INSERT INTO users (user_id, credits, last_activity) VALUES (?, ?, datetime('now'))", (str(user_id), amount))
    conn.commit()
    conn.close()

def count_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

# --- СИСТЕМА БОНУСОВ ---
BONUS_FILE = "claimed_bonuses.txt"
BONUS_AMOUNT = 6

def check_and_give_bonus(user_id):
    """Проверяет, получал ли юзер бонус за подписку. Если нет - дает 6 кредитов."""
    if not os.path.exists(BONUS_FILE):
        open(BONUS_FILE, 'w').close()
    
    with open(BONUS_FILE, 'r', encoding='utf-8') as f:
        claimed = f.read().splitlines()
        
    if str(user_id) not in claimed:
        add_credits(user_id, BONUS_AMOUNT)
        with open(BONUS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{user_id}\n")
        return True
    return False

# --- ФУНКЦИИ ВК ---
def send_message(user_id, message, keyboard=None):
    params = {
        "user_id": user_id,
        "message": message,
        "random_id": random.randint(0, 2**32)
    }
    if keyboard: 
        try:
            params["keyboard"] = keyboard.get_keyboard()
        except AttributeError:
            params["keyboard"] = keyboard

    try: 
        vk.messages.send(**params)
    except Exception as e: 
        print(f"Ошибка отправки сообщения {user_id}: {e}")

def get_app_keyboard():
    keyboard = VkKeyboard(inline=True)
    keyboard.add_openlink_button(
        label="🧠 Открыть Нейро-Репетитор",
        link="https://vk.com/app54451631"
    )
    return keyboard

# --- ГЛАВНЫЙ ЦИКЛ БОТА ---
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        original_text = event.text.strip()
        text = original_text.lower()

        # ---------------- СЕКРЕТНАЯ АДМИНКА ----------------
        if user_id == ADMIN_VK_ID:
            
            # 1. Выдать кредиты
            if text.startswith("выдать"):
                try:
                    parts = text.split()
                    target_id = int(parts[1])
                    amount = int(parts[2])
                    
                    add_credits(target_id, amount)
                    new_balance = get_balance(target_id)
                    send_message(user_id, f"✅ Успешно!\nУченику @id{target_id} начислено {amount} кр.\nЕго баланс: {new_balance} кр.")
                except Exception as e:
                    send_message(user_id, "❌ Формат: выдать 12345678 50")
                continue
                
            # 2. Проверить баланс
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
                
            # 3. Статистика
            elif text == "стата" or text == "статистика":
                try:
                    total_users = count_users()
                    with open(BONUS_FILE, 'r') as f:
                        subscribers = len(f.read().splitlines())
                    send_message(user_id, f"📊 СТАТИСТИКА РЕПЕТИТОРА:\n\n👥 Всего в базе: {total_users} чел.\n🔔 Получили бонус (подписчики): {subscribers} чел.")
                except Exception as e:
                    send_message(user_id, f"❌ Ошибка: {e}")
                continue
                
            # 4. Умная рассылка по ВСЕЙ БАЗЕ
            elif text.startswith("рассылка"):
                try:
                    broadcast_text = original_text[9:].strip() 
                    
                    # Получаем вложения из сообщения админа
                    attachments = []
                    if hasattr(event, 'attachments'):
                        for key, value in event.attachments.items():
                            if key.startswith('attach') and key.endswith('_type') and value == 'photo':
                                photo_id = event.attachments[key.replace('_type', '')]
                                attachments.append(f"photo{photo_id}")
                    att_string = ",".join(attachments) if attachments else None

                    users = get_all_users()
                    if not users:
                        send_message(user_id, "❌ База данных пуста!")
                        continue

                    success_count = 0
                    error_count = 0
                    
                    send_message(user_id, f"⏳ Начинаю рассылку по базе: {len(users)} чел.")
                    
                    for user_db_id in users:
                        try:
                            vk.messages.send(
                                user_id=int(user_db_id),
                                message=broadcast_text,
                                attachment=att_string,
                                random_id=random.randint(0, 2**31)
                            )
                            success_count += 1
                            time.sleep(0.1) # Пауза, чтобы ВК не забанил за спам
                        except Exception:
                            error_count += 1
                            continue 
                    
                    send_message(user_id, f"✅ Рассылка завершена!\n\n📈 Статистика:\n— Успешно: {success_count}\n— Ошибок (закрыли ЛС): {error_count}\n— Всего: {len(users)}")
                except Exception as e:
                    send_message(user_id, f"❌ Критическая ошибка рассылки: {e}")
                continue

        # ---------------- КОНЕЦ АДМИНКИ ----------------

        # --- ЕДИНЫЙ ОТВЕТ БОТА ДЛЯ УЧЕНИКОВ ---
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
