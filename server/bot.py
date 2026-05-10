import telebot
from groq import Groq
import requests
import json
import os
import time

# ========== КЛЮЧИ ==========
BOT_TOKEN  = os.environ.get("BOT_TOKEN")
GROQ_KEY   = os.environ.get("GROQ_API_KEY")
SERVER_URL = "https://agrosynapse.onrender.com"

bot    = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_KEY)

user_data     = {}
waiting_input = {}
camera_requests = {}

def get_stations(chat_id):
    return user_data.get(chat_id, {}).get("stations", {})

def get_station(chat_id, station_id):
    return get_stations(chat_id).get(station_id, {})

def save_chat_id(chat_id: int):
    chats_file = "telegram_chats.txt"
    existing = []
    if os.path.exists(chats_file):
        with open(chats_file, "r") as f:
            existing = f.read().splitlines()
    if str(chat_id) not in existing:
        with open(chats_file, "a") as f:
            f.write(str(chat_id) + "\n")
        print(f"✅ Новый подписчик: {chat_id}")

# ========== СТАРТ ==========
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {"stations": {}, "current_station": None}
    waiting_input[chat_id] = None
    save_chat_id(chat_id)

    bot.send_message(chat_id,
        "🌱 Привет! Я AgroSynapse бот!\n\n"
        "Управляю поливом и слежу за растениями.\n\n"
        "Команды:\n"
        "➕ /addstation — добавить станцию\n"
        "📊 /status — показатели станции\n"
        "💧 /water — управление поливом\n"
        "🌱 /mystations — мои станции\n"
        "🚁 /camera — живое фото с дрона\n"
        "🔍 /drone — последний анализ дрона\n"
    )

# ========== ДОБАВИТЬ СТАНЦИЮ ==========
@bot.message_handler(commands=['addstation'])
def add_station(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"stations": {}, "current_station": None}
    waiting_input[chat_id] = None

    markup = telebot.types.InlineKeyboardMarkup()
    for i in range(1, 4):
        stations = get_stations(chat_id)
        if i in stations:
            label = f"✅ Станция {i}: {stations[i]['plant']}"
        else:
            label = f"➕ Станция {i}"
        markup.add(telebot.types.InlineKeyboardButton(
            label, callback_data=f"setup_{i}"
        ))

    bot.send_message(chat_id,
        "🏭 Выбери станцию для настройки:",
        reply_markup=markup
    )

# ========== ВЫБОР СТАНЦИИ ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("setup_"))
def setup_station(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])

    if chat_id not in user_data:
        user_data[chat_id] = {"stations": {}, "current_station": None}

    user_data[chat_id]["current_station"] = station_id
    waiting_input[chat_id] = "plant"

    bot.send_message(chat_id,
        f"🌱 Настройка Станции {station_id}\n\n"
        f"Какое растение на этой станции?\n"
        f"(например: картошка, огурец, помидор)"
    )

# ========== МОИ СТАНЦИИ ==========
@bot.message_handler(commands=['mystations'])
def my_stations(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None

    if not stations:
        bot.send_message(chat_id,
            "У тебя нет станций!\n➕ /addstation"
        )
        return

    text = "🏭 Твои станции:\n\n"
    for sid, data in stations.items():
        text += (
            f"📍 Станция {sid}:\n"
            f"   🌱 {data.get('plant','?')} ({data.get('sorts','?')})\n"
            f"   📍 {data.get('region','?')}\n"
            f"   💧 {data.get('norms',{}).get('water_ml','?')} мл/день\n\n"
        )

    bot.send_message(chat_id, text)

# ========== СТАТУС ==========
@bot.message_handler(commands=['status'])
def status(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None

    if not stations:
        bot.send_message(chat_id, "Сначала добавь станцию!\n➕ /addstation")
        return

    markup = telebot.types.InlineKeyboardMarkup()
    for sid, data in stations.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"🌱 Станция {sid}: {data.get('plant','?')}",
            callback_data=f"status_{sid}"
        ))

    bot.send_message(chat_id, "📊 Какую станцию показать?",
                     reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("status_"))
def show_status(call):
    chat_id    = call.message.chat.id
    station_id = call.data.split("_")[1]

    try:
        s = requests.get(
            f"{SERVER_URL}/station/data/{station_id}/last", timeout=10
        ).json()
        r = requests.get(
            f"{SERVER_URL}/robot/data/{station_id}/last", timeout=10
        ).json()
        plant = get_station(chat_id, int(station_id)).get('plant', '?')

        bot.send_message(chat_id,
            f"📊 Станция {station_id} ({plant}):\n\n"
            f"🌡 Температура: {s.get('temp','?')}°C\n"
            f"☀️ Свет: {s.get('light','?')}%\n"
            f"💧 Влажность почвы: {r.get('soil_moisture','?')}%\n"
            f"🧪 pH: {r.get('ph','?')}\n"
        )
    except Exception as e:
        print(f"Статус ошибка: {e}")
        bot.send_message(chat_id, "⚠️ Нет данных с этой станции")

# ========== ПОЛИВ ==========
@bot.message_handler(commands=['water'])
def water(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None

    if not stations:
        bot.send_message(chat_id, "Сначала добавь станцию!\n➕ /addstation")
        return

    markup = telebot.types.InlineKeyboardMarkup()
    for sid, data in stations.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"💧 Станция {sid}: {data.get('plant','?')}",
            callback_data=f"water_{sid}"
        ))

    bot.send_message(chat_id, "💧 Какую станцию полить?",
                     reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("water_"))
def do_water(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    ml = get_station(chat_id, station_id).get("norms", {}).get("water_ml", 100)

    try:
        requests.post(
            f"{SERVER_URL}/station/config/{station_id}",
            params={"watering_ml": ml}
        )
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(
            f"⛔ Стоп полив Станции {station_id}",
            callback_data=f"stop_{station_id}"
        ))
        bot.send_message(chat_id,
            f"✅ Полив запущен!\n"
            f"💧 Станция {station_id} польёт {ml} мл.",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Полив ошибка: {e}")
        bot.send_message(chat_id, "⚠️ Ошибка отправки команды")

@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_"))
def stop_water(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])

    try:
        requests.post(
            f"{SERVER_URL}/station/config/{station_id}",
            params={"watering_ml": 0}
        )
        bot.edit_message_reply_markup(
            chat_id, call.message.message_id, reply_markup=None
        )
        bot.send_message(chat_id,
            f"⛔ Полив Станции {station_id} остановлен!"
        )
    except Exception as e:
        print(f"Стоп ошибка: {e}")
        bot.send_message(chat_id, "⚠️ Ошибка остановки")

# ========== ЖИВАЯ КАМЕРА ДРОНА ==========
@bot.message_handler(commands=['camera'])
def camera(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None

    if not stations:
        bot.send_message(chat_id,
            "Сначала добавь станцию!\n➕ /addstation"
        )
        return

    markup = telebot.types.InlineKeyboardMarkup()
    for sid, data in stations.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"🚁 Дрон Станции {sid}: {data.get('plant','?')}",
            callback_data=f"camera_{sid}"
        ))

    bot.send_message(chat_id,
        "📡 С какого дрона показать живое фото?",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("camera_"))
def request_camera(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    plant      = get_station(chat_id, station_id).get('plant', '?')

    msg = bot.send_message(chat_id,
        f"📡 Запрашиваю живое фото дрона...\n"
        f"🚁 Станция {station_id} ({plant})\n\n"
        f"⏳ Жди 10-15 секунд..."
    )

    # Отправляем запрос дрону
    try:
        requests.get(
            f"{SERVER_URL}/drone/request/{station_id}",
            timeout=5
        )
    except Exception as e:
        print(f"Запрос дрона ошибка: {e}")

    # Сохраняем кто ждёт фото
    camera_requests[station_id] = {
        "chat_id":    chat_id,
        "message_id": msg.message_id,
        "time":       time.time()
    }

    # Ждём фото в отдельном потоке
    import threading
    t = threading.Thread(
        target=wait_for_photo,
        args=(chat_id, station_id, msg.message_id),
        daemon=True
    )
    t.start()

def wait_for_photo(chat_id, station_id, msg_id):
    # Ждём максимум 30 секунд
    for i in range(30):
        time.sleep(1)
        try:
            r = requests.get(
                f"{SERVER_URL}/drone/last/{station_id}",
                timeout=5
            ).json()

            if "error" not in r and r.get("image_path"):
                # Фото пришло! Редактируем сообщение
                bot.edit_message_text(
                    f"✅ Фото получено!\n"
                    f"🤖 Анализ:\n\n{r.get('analysis','Нет анализа')}\n\n"
                    f"📅 {r.get('created_at','?')}",
                    chat_id=chat_id,
                    message_id=msg_id
                )
                return
        except Exception as e:
            print(f"Ожидание фото: {e}")

    # Таймаут
    try:
        bot.edit_message_text(
            "⚠️ Дрон не ответил. Возможно он не в зоне WiFi.",
            chat_id=chat_id,
            message_id=msg_id
        )
    except:
        pass

# ========== ПОСЛЕДНИЙ АНАЛИЗ ДРОНА ==========
@bot.message_handler(commands=['drone'])
def drone_status(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None

    if not stations:
        bot.send_message(chat_id,
            "Сначала добавь станцию!\n➕ /addstation"
        )
        return

    markup = telebot.types.InlineKeyboardMarkup()
    for sid, data in stations.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"🚁 Станция {sid}: {data.get('plant','?')}",
            callback_data=f"drone_{sid}"
        ))

    bot.send_message(chat_id,
        "🔍 Последний анализ с какого дрона?",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("drone_"))
def show_drone(call):
    chat_id    = call.message.chat.id
    station_id = call.data.split("_")[1]

    try:
        r = requests.get(
            f"{SERVER_URL}/drone/last/{station_id}",
            timeout=10
        ).json()

        if "error" in r:
            bot.send_message(chat_id,
                "⚠️ Дрон ещё не прислал данные"
            )
            return

        bot.send_message(chat_id,
            f"🚁 Последний анализ дрона\n"
            f"Станция {station_id}:\n\n"
            f"🤖 {r.get('analysis','Нет анализа')}\n\n"
            f"📅 {r.get('created_at','?')}"
        )
    except Exception as e:
        print(f"Дрон ошибка: {e}")
        bot.send_message(chat_id, "⚠️ Ошибка получения данных")

# ========== ПОДТВЕРЖДЕНИЕ СОРТА ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_"))
def confirm_station(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    plant      = user_data[chat_id]["stations"][station_id]["plant"]
    region     = user_data[chat_id]["stations"][station_id]["region"]

    bot.edit_message_reply_markup(
        chat_id, call.message.message_id, reply_markup=None
    )
    bot.send_message(chat_id, "⚙️ Настраиваю нормы полива...")
    setup_norms(chat_id, station_id, plant, region)

@bot.callback_query_handler(func=lambda c: c.data.startswith("manual_sort_"))
def manual_sort(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[2])
    plant      = user_data[chat_id]["stations"][station_id]["plant"]

    bot.edit_message_reply_markup(
        chat_id, call.message.message_id, reply_markup=None
    )
    waiting_input[chat_id] = f"sort_{station_id}"
    bot.send_message(chat_id,
        f"🌱 Какой сорт {plant} у тебя?\n\n"
        f"Напиши название или скинь фото 📸"
    )

# ========== НАСТРОЙКА НОРМ ==========
def setup_norms(chat_id, station_id, plant, region):
    sort = user_data[chat_id]["stations"][station_id].get("sorts", "")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Для растения {plant} сорт {sort} в регионе {region}. "
                    f"Дай нормы ТОЛЬКО в JSON: "
                    f"{{\"water_ml\": число, \"temp\": число, "
                    f"\"light\": число, \"ph\": число}}"
                )
            }]
        )
        norms_text = response.choices[0].message.content
        start = norms_text.find('{')
        end   = norms_text.rfind('}') + 1
        norms = json.loads(norms_text[start:end])
    except Exception as e:
        print(f"Groq ошибка: {e}")
        norms = {"water_ml": 200, "temp": 20, "light": 60, "ph": 6.5}

    user_data[chat_id]["stations"][station_id]["norms"] = norms

    # Сбрасываем полив до 0 при настройке
    try:
        requests.post(
            f"{SERVER_URL}/station/config/{station_id}",
            params={"watering_ml": 0}
        )
    except Exception as e:
        print(f"Сервер ошибка: {e}")

    bot.send_message(chat_id,
        f"✅ Станция {station_id} настроена!\n\n"
        f"🌱 Растение: {plant}\n"
        f"📍 Регион: {region}\n"
        f"💧 Норма воды: {norms['water_ml']} мл/день\n"
        f"🌡 Температура: {norms['temp']}°C\n"
        f"☀️ Свет: {norms['light']}%\n"
        f"🧪 pH: {norms['ph']}\n\n"
        f"➕ /addstation — добавить ещё\n"
        f"📊 /status — показатели\n"
        f"🚁 /camera — живое фото дрона"
    )
    waiting_input[chat_id] = None

# ========== ВСЕ СООБЩЕНИЯ ==========
@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"stations": {}, "current_station": None}
    if chat_id not in waiting_input:
        waiting_input[chat_id] = None

    state      = waiting_input.get(chat_id)
    station_id = user_data[chat_id].get("current_station")
    text       = message.text if message.content_type == 'text' else ""

    # ===== НАСТРОЙКА СТАНЦИИ =====
    if state == "plant" and station_id:
        plant = text
        if station_id not in user_data[chat_id]["stations"]:
            user_data[chat_id]["stations"][station_id] = {}
        user_data[chat_id]["stations"][station_id]["plant"] = plant
        waiting_input[chat_id] = "region"
        bot.send_message(chat_id,
            f"📍 В каком регионе Станция {station_id}?\n"
            f"(например: Уральск, Алматы)"
        )
        return

    if state == "region" and station_id:
        region = text
        plant  = user_data[chat_id]["stations"][station_id]["plant"]
        user_data[chat_id]["stations"][station_id]["region"] = region
        waiting_input[chat_id] = None

        bot.send_message(chat_id, "🤖 Анализирую растение...")

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Назови 2-3 популярных сорта {plant} "
                        f"для региона {region}. "
                        f"Только названия через запятую."
                    )
                }]
            )
            sorts = response.choices[0].message.content
        except:
            sorts = "сорт не определён"

        user_data[chat_id]["stations"][station_id]["sorts"] = sorts

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton(
                "✅ Да", callback_data=f"confirm_{station_id}"
            ),
            telebot.types.InlineKeyboardButton(
                "❌ Нет", callback_data=f"manual_sort_{station_id}"
            )
        )
        bot.send_message(chat_id,
            f"🌱 Для {plant} в {region} популярны:\n\n"
            f"{sorts}\n\n"
            f"Один из этих сортов у тебя?",
            reply_markup=markup
        )
        return

    if state and state.startswith("sort_"):
        station_id = int(state.split("_")[1])
        plant  = user_data[chat_id]["stations"][station_id]["plant"]
        region = user_data[chat_id]["stations"][station_id]["region"]

        if message.content_type == 'photo':
            bot.send_message(chat_id, "📸 Анализирую фото...")
            file_id   = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            file_url  = (
                f"https://api.telegram.org/file/"
                f"bot{BOT_TOKEN}/{file_info.file_path}"
            )
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    max_tokens=100,
                    messages=[{
                        "role": "user",
                        "content": (
                            f"На фото растение {plant}. "
                            f"Фото: {file_url}. "
                            f"Определи сорт одним предложением на русском."
                        )
                    }]
                )
                sort_name = response.choices[0].message.content
            except:
                sort_name = plant
        else:
            sort_name = text

        user_data[chat_id]["stations"][station_id]["sorts"] = sort_name
        bot.send_message(chat_id, f"✅ Сорт сохранён: {sort_name}")
        bot.send_message(chat_id, "⚙️ Настраиваю нормы полива...")
        setup_norms(chat_id, station_id, plant, region)
        return

    # ===== ФОТО ОТ ПОЛЬЗОВАТЕЛЯ =====
    if message.content_type == 'photo':
        stations = get_stations(chat_id)
        if not stations:
            bot.send_message(chat_id,
                "Сначала добавь станцию!\n➕ /addstation"
            )
            return

        markup = telebot.types.InlineKeyboardMarkup()
        for sid, data in stations.items():
            markup.add(telebot.types.InlineKeyboardButton(
                f"🌱 Станция {sid}: {data.get('plant','?')}",
                callback_data=f"photo_{sid}"
            ))

        user_data[chat_id]["pending_photo"] = message
        bot.send_message(chat_id,
            "📸 Для какой станции это фото?",
            reply_markup=markup
        )
        return

    # ===== ОБЫЧНЫЙ ВОПРОС К ИИ =====
    stations    = get_stations(chat_id)
    plants_info = ""
    if stations:
        for sid, data in stations.items():
            plants_info += (
                f"Станция {sid}: {data.get('plant','?')} "
                f"в {data.get('region','?')}\n"
            )
    else:
        plants_info = "растения не указаны"

    bot.send_chat_action(chat_id, 'typing')

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты агроном-помощник системы AgroSynapse. "
                        "Помогаешь ухаживать за растениями. "
                        "Отвечай на русском коротко и понятно."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Мои растения:\n{plants_info}\n\n"
                        f"Вопрос: {text}"
                    )
                }
            ]
        )
        answer = response.choices[0].message.content
    except Exception as e:
        print(f"Groq ошибка: {e}")
        answer = "⚠️ Не удалось получить ответ. Попробуй позже."

    markup = None
    if stations:
        markup = telebot.types.InlineKeyboardMarkup()
        for sid, data in stations.items():
            markup.add(telebot.types.InlineKeyboardButton(
                f"💧 Полить Станцию {sid}: {data.get('plant','?')}",
                callback_data=f"water_{sid}"
            ))

    bot.send_message(chat_id, f"🤖 {answer}", reply_markup=markup)

# ========== ФОТО АНАЛИЗ ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("photo_"))
def process_photo(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    message    = user_data[chat_id].get("pending_photo")
    plant      = get_station(chat_id, station_id).get('plant', 'растение')

    bot.send_message(chat_id, "🤖 Анализирую фото...")

    file_id   = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    file_url  = (
        f"https://api.telegram.org/file/"
        f"bot{BOT_TOKEN}/{file_info.file_path}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"Пользователь прислал фото растения {plant} "
                    f"со Станции {station_id}. "
                    f"Фото: {file_url}. "
                    f"Определи проблемы и дай рекомендации. "
                    f"Отвечай на русском коротко."
                )
            }]
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        print(f"Фото ошибка: {e}")
        analysis = "Не удалось проанализировать фото."

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        f"💧 Полить Станцию {station_id}",
        callback_data=f"water_{station_id}"
    ))

    bot.send_message(chat_id,
        f"🔍 Анализ Станции {station_id} ({plant}):\n\n{analysis}",
        reply_markup=markup
    )
