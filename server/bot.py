import telebot
import requests
import json
import os
import time
import threading

BOT_TOKEN   = os.environ.get("BOT_TOKEN")
OPENAI_KEY  = os.environ.get("OPENAI_API_KEY")
SERVER_URL  = "https://agrosynapse.onrender.com"

bot = telebot.TeleBot(BOT_TOKEN)

user_data     = {}
waiting_input = {}

def ai(prompt, system="Ты агроном AgroSynapse. Отвечай на русском коротко. Никогда не выдумывай IP-адреса, пароли и технические данные. Отвечай только на вопросы об агрономии и растениях."):
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt}
                ],
                "max_tokens": 400
            },
            timeout=30
        )
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"OpenAI ошибка: {e}")
        return "⚠️ Попробуй позже."

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

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {"stations": {}, "current_station": None}
    waiting_input[chat_id] = None
    save_chat_id(chat_id)
    bot.send_message(chat_id,
        "🌱 Привет! Я AgroSynapse бот!\n\n"
        "Команды:\n"
        "➕ /addstation — добавить станцию\n"
        "📊 /status — показатели станции\n"
        "💧 /water — управление поливом\n"
        "🌱 /mystations — мои станции\n"
        "🚁 /camera — живое фото с дрона\n"
        "🔍 /drone — последний анализ дрона\n"
    )

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
    bot.send_message(chat_id, "🏭 Выбери станцию:", reply_markup=markup)

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
        f"Какое растение?\n(картошка, огурец, помидор)"
    )

@bot.message_handler(commands=['mystations'])
def my_stations(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None
    if not stations:
        bot.send_message(chat_id, "Нет станций!\n➕ /addstation")
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
    bot.send_message(chat_id, "📊 Какую станцию показать?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("status_"))
def show_status(call):
    chat_id    = call.message.chat.id
    station_id = call.data.split("_")[1]
    try:
        s = requests.get(f"{SERVER_URL}/station/data/{station_id}/last", timeout=10).json()
        r = requests.get(f"{SERVER_URL}/robot/data/{station_id}/last",   timeout=10).json()
        plant = get_station(chat_id, int(station_id)).get('plant', '?')
        bot.send_message(chat_id,
            f"📊 Станция {station_id} ({plant}):\n\n"
            f"🌡 Температура: {s.get('temp','?')}°C\n"
            f"☀️ Свет: {s.get('light','?')}%\n"
            f"💧 Влажность почвы: {r.get('soil_moisture','?')}%\n"
            f"🧪 pH: {r.get('ph','?')}\n"
        )
    except:
        bot.send_message(chat_id, "⚠️ Нет данных")

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
    bot.send_message(chat_id, "💧 Какую станцию полить?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("water_"))
def do_water(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    ml = get_station(chat_id, station_id).get("norms", {}).get("water_ml", 100)
    try:
        requests.post(f"{SERVER_URL}/station/config/{station_id}",
                     params={"watering_ml": ml})
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(
            f"⛔ Стоп Станции {station_id}",
            callback_data=f"stop_{station_id}"
        ))
        bot.send_message(chat_id,
            f"✅ Полив запущен!\n💧 Станция {station_id} → {ml} мл.",
            reply_markup=markup
        )
    except:
        bot.send_message(chat_id, "⚠️ Ошибка")

@bot.callback_query_handler(func=lambda c: c.data.startswith("stop_"))
def stop_water(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    try:
        requests.post(f"{SERVER_URL}/station/config/{station_id}",
                     params={"watering_ml": 0})
        bot.edit_message_reply_markup(chat_id, call.message.message_id,
                                      reply_markup=None)
        bot.send_message(chat_id, f"⛔ Полив Станции {station_id} остановлен!")
    except:
        bot.send_message(chat_id, "⚠️ Ошибка остановки")

@bot.message_handler(commands=['camera'])
def camera(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None
    if not stations:
        bot.send_message(chat_id, "Сначала добавь станцию!\n➕ /addstation")
        return
    markup = telebot.types.InlineKeyboardMarkup()
    for sid, data in stations.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"🚁 Дрон Станции {sid}: {data.get('plant','?')}",
            callback_data=f"camera_{sid}"
        ))
    bot.send_message(chat_id, "📡 С какого дрона показать фото?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("camera_"))
def request_camera(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    plant      = get_station(chat_id, station_id).get('plant', '?')
    msg = bot.send_message(chat_id,
        f"📡 Запрашиваю фото дрона...\n"
        f"🚁 Станция {station_id} ({plant})\n"
        f"⏳ Жди 10-15 секунд..."
    )
    try:
        requests.get(f"{SERVER_URL}/drone/request/{station_id}", timeout=5)
    except:
        pass
    t = threading.Thread(
        target=wait_for_photo,
        args=(chat_id, station_id, msg.message_id),
        daemon=True
    )
    t.start()

def wait_for_photo(chat_id, station_id, msg_id):
    for i in range(30):
        time.sleep(1)
        try:
            r = requests.get(
                f"{SERVER_URL}/drone/last/{station_id}", timeout=5
            ).json()
            if "error" not in r and r.get("image_path"):
                bot.edit_message_text(
                    f"✅ Фото получено!\n\n"
                    f"🤖 Анализ:\n{r.get('analysis','?')}\n\n"
                    f"📅 {r.get('created_at','?')}",
                    chat_id=chat_id,
                    message_id=msg_id
                )
                return
        except:
            pass
    try:
        bot.edit_message_text(
            "⚠️ Дрон не ответил. Не в зоне WiFi.",
            chat_id=chat_id,
            message_id=msg_id
        )
    except:
        pass

@bot.message_handler(commands=['drone'])
def drone_status(message):
    chat_id  = message.chat.id
    stations = get_stations(chat_id)
    waiting_input[chat_id] = None
    if not stations:
        bot.send_message(chat_id, "Сначала добавь станцию!\n➕ /addstation")
        return
    markup = telebot.types.InlineKeyboardMarkup()
    for sid, data in stations.items():
        markup.add(telebot.types.InlineKeyboardButton(
            f"🚁 Станция {sid}: {data.get('plant','?')}",
            callback_data=f"drone_{sid}"
        ))
    bot.send_message(chat_id, "🔍 Последний анализ дрона:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("drone_"))
def show_drone(call):
    chat_id    = call.message.chat.id
    station_id = call.data.split("_")[1]
    try:
        r = requests.get(
            f"{SERVER_URL}/drone/last/{station_id}", timeout=10
        ).json()
        if "error" in r:
            bot.send_message(chat_id, "⚠️ Дрон ещё не прислал данные")
            return
        bot.send_message(chat_id,
            f"🚁 Последний анализ дрона\n"
            f"Станция {station_id}:\n\n"
            f"🤖 {r.get('analysis','?')}\n\n"
            f"📅 {r.get('created_at','?')}"
        )
    except:
        bot.send_message(chat_id, "⚠️ Ошибка получения данных")

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_"))
def confirm_station(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    bot.send_message(chat_id, "⚙️ Настраиваю нормы полива...")
    plant  = user_data[chat_id]["stations"][station_id]["plant"]
    region = user_data[chat_id]["stations"][station_id]["region"]
    setup_norms(chat_id, station_id, plant, region)

@bot.callback_query_handler(func=lambda c: c.data.startswith("manual_sort_"))
def manual_sort(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[2])
    plant      = user_data[chat_id]["stations"][station_id]["plant"]
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    waiting_input[chat_id] = f"sort_{station_id}"
    bot.send_message(chat_id, f"🌱 Какой сорт {plant}?\n\nНапиши или скинь фото 📸")

def setup_norms(chat_id, station_id, plant, region):
    sort = user_data[chat_id]["stations"][station_id].get("sorts", "")
    try:
        norms_text = ai(
            f"Для {plant} сорт {sort} в регионе {region}. "
            f"Дай нормы ТОЛЬКО в JSON без markdown: "
            f"{{\"water_ml\": число, \"temp\": число, \"light\": число, \"ph\": число}}",
            system="Отвечай только JSON без markdown и пояснений."
        )
        start = norms_text.find('{')
        end   = norms_text.rfind('}') + 1
        norms = json.loads(norms_text[start:end])
    except:
        norms = {"water_ml": 200, "temp": 20, "light": 60, "ph": 6.5}
    user_data[chat_id]["stations"][station_id]["norms"] = norms
    try:
        requests.post(f"{SERVER_URL}/station/config/{station_id}",
                     params={"watering_ml": 0})
    except:
        pass
    bot.send_message(chat_id,
        f"✅ Станция {station_id} настроена!\n\n"
        f"🌱 {plant} | 📍 {region}\n"
        f"💧 {norms['water_ml']} мл/день\n"
        f"🌡 {norms['temp']}°C | ☀️ {norms['light']}% | 🧪 pH {norms['ph']}\n\n"
        f"➕ /addstation | 📊 /status | 🚁 /camera"
    )
    waiting_input[chat_id] = None

@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message):
    chat_id = message.chat.id

    if message.content_type == 'text' and message.text.startswith('/'):
        return

    if chat_id not in user_data:
        user_data[chat_id] = {"stations": {}, "current_station": None}
    if chat_id not in waiting_input:
        waiting_input[chat_id] = None

    state      = waiting_input.get(chat_id)
    station_id = user_data[chat_id].get("current_station")
    text       = message.text if message.content_type == 'text' else ""

    if state == "plant" and station_id:
        if station_id not in user_data[chat_id]["stations"]:
            user_data[chat_id]["stations"][station_id] = {}
        user_data[chat_id]["stations"][station_id]["plant"] = text
        waiting_input[chat_id] = "region"
        bot.send_message(chat_id,
            f"📍 В каком регионе Станция {station_id}?\n(Уральск, Алматы)"
        )
        return

    if state == "region" and station_id:
        region = text
        plant  = user_data[chat_id]["stations"][station_id]["plant"]
        user_data[chat_id]["stations"][station_id]["region"] = region
        waiting_input[chat_id] = None
        bot.send_message(chat_id, "🤖 Анализирую растение...")
        sorts = ai(f"Назови 2-3 популярных сорта {plant} для {region}. Только названия через запятую.")
        user_data[chat_id]["stations"][station_id]["sorts"] = sorts
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("✅ Да", callback_data=f"confirm_{station_id}"),
            telebot.types.InlineKeyboardButton("❌ Нет", callback_data=f"manual_sort_{station_id}")
        )
        bot.send_message(chat_id,
            f"🌱 Для {plant} в {region} популярны:\n\n{sorts}\n\n"
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
            file_url  = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            sort_name = ai(f"На фото {plant}. Фото: {file_url}. Определи сорт одним предложением на русском.")
        else:
            sort_name = text
        user_data[chat_id]["stations"][station_id]["sorts"] = sort_name
        bot.send_message(chat_id, f"✅ Сорт: {sort_name}")
        bot.send_message(chat_id, "⚙️ Настраиваю нормы...")
        setup_norms(chat_id, station_id, plant, region)
        return

    if message.content_type == 'photo':
        stations = get_stations(chat_id)
        if not stations:
            bot.send_message(chat_id, "Сначала добавь станцию!\n➕ /addstation")
            return
        markup = telebot.types.InlineKeyboardMarkup()
        for sid, data in stations.items():
            markup.add(telebot.types.InlineKeyboardButton(
                f"🌱 Станция {sid}: {data.get('plant','?')}",
                callback_data=f"photo_{sid}"
            ))
        user_data[chat_id]["pending_photo"] = message
        bot.send_message(chat_id, "📸 Для какой станции фото?", reply_markup=markup)
        return

    stations    = get_stations(chat_id)
    plants_info = ""
    if stations:
        for sid, data in stations.items():
            plants_info += f"Станция {sid}: {data.get('plant','?')} в {data.get('region','?')}\n"
    else:
        plants_info = "растения не указаны"

    bot.send_chat_action(chat_id, 'typing')
    answer = ai(f"Мои растения:\n{plants_info}\n\nВопрос: {text}")

    markup = None
    if stations:
        markup = telebot.types.InlineKeyboardMarkup()
        for sid, data in stations.items():
            markup.add(telebot.types.InlineKeyboardButton(
                f"💧 Полить Станцию {sid}: {data.get('plant','?')}",
                callback_data=f"water_{sid}"
            ))
    bot.send_message(chat_id, f"🤖 {answer}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("photo_"))
def process_photo(call):
    chat_id    = call.message.chat.id
    station_id = int(call.data.split("_")[1])
    message    = user_data[chat_id].get("pending_photo")
    plant      = get_station(chat_id, station_id).get('plant', 'растение')
    bot.send_message(chat_id, "🤖 Анализирую фото...")
    file_id   = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    file_url  = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    analysis  = ai(f"Фото растения {plant} со Станции {station_id}. Фото: {file_url}. Проблемы и рекомендации на русском.")
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        f"💧 Полить Станцию {station_id}",
        callback_data=f"water_{station_id}"
    ))
    bot.send_message(chat_id,
        f"🔍 Анализ Станции {station_id} ({plant}):\n\n{analysis}",
        reply_markup=markup
    )
