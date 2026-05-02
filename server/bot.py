import telebot
from groq import Groq
import requests
import os

# ========== КЛЮЧИ ==========
BOT_TOKEN  = "8705551830:AAEzTtIvFucE_Homl61QEa6m1Uq8xDM1O1c"
GROQ_KEY   = "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"
SERVER_URL = "https://agrosynapse.onrender.com"

bot    = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_KEY)

# Профиль растения пользователя
user_profiles = {}

# ========== СТАРТ ==========
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, 
        "🌱 Привет! Я AgroSynapse бот!\n\n"
        "Я помогу тебе ухаживать за растениями.\n\n"
        "Для начала — какое у тебя растение? 🌿\n"
        "Напиши название (например: картошка, помидор, огурец)"
    )
    bot.register_next_step_handler(message, get_plant)

# ========== ШАГ 1: РАСТЕНИЕ ==========
def get_plant(message):
    chat_id = message.chat.id
    plant = message.text
    user_profiles[chat_id] = {"plant": plant}
    
    bot.send_message(chat_id,
        f"🌍 Отлично! У тебя {plant}.\n\n"
        f"В каком регионе ты живёшь?\n"
        f"Напиши город или регион (например: Уральск, Алматы)"
    )
    bot.register_next_step_handler(message, get_region)

# ========== ШАГ 2: РЕГИОН ==========
def get_region(message):
    chat_id = message.chat.id
    region = message.text
    user_profiles[chat_id]["region"] = region
    
    plant  = user_profiles[chat_id]["plant"]
    
    # Спрашиваем ИИ про растение
    bot.send_message(chat_id, "🤖 Анализирую...")
    
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{
            "role": "user",
            "content": f"Пользователь говорит что у него растёт {plant} в регионе {region}. "
                      f"Назови 2-3 самых популярных сорта этого растения для этого региона. "
                      f"Отвечай коротко, только названия сортов через запятую."
        }]
    )
    
    sorts = response.choices[0].message.content
    user_profiles[chat_id]["sorts"] = sorts
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Да", callback_data="confirm_plant"),
        telebot.types.InlineKeyboardButton("❌ Нет, другой", callback_data="retry_plant")
    )
    
    bot.send_message(chat_id,
        f"🌱 Для {plant} в регионе {region} популярны такие сорта:\n\n"
        f"{sorts}\n\n"
        f"Один из этих сортов у тебя?",
        reply_markup=markup
    )

# ========== ПОДТВЕРЖДЕНИЕ СОРТА ==========
@bot.callback_query_handler(func=lambda c: c.data in ["confirm_plant", "retry_plant"])
def confirm_plant(call):
    chat_id = call.message.chat.id
    
    if call.data == "retry_plant":
        bot.send_message(chat_id, "Напиши точное название своего растения и сорт:")
        bot.register_next_step_handler(call.message, get_plant)
        return
    
    plant  = user_profiles[chat_id]["plant"]
    region = user_profiles[chat_id]["region"]
    
    # ИИ настраивает нормы полива
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{
            "role": "user", 
            "content": f"Для растения {plant} в регионе {region} дай точные нормы: "
                      f"сколько мл воды в день, оптимальная температура, "
                      f"оптимальный уровень освещения в процентах, оптимальный pH. "
                      f"Отвечай ТОЛЬКО в формате JSON: "
                      f"{{\"water_ml\": число, \"temp\": число, \"light\": число, \"ph\": число}}"
        }]
    )
    
    import json
    try:
        norms_text = response.choices[0].message.content
        # Убираем лишнее из ответа
        start = norms_text.find('{')
        end   = norms_text.rfind('}') + 1
        norms = json.loads(norms_text[start:end])
        user_profiles[chat_id]["norms"] = norms
        
        # Сохраняем нормы на сервер
        requests.post(f"{SERVER_URL}/station/config/1", 
                     params={"watering_ml": norms["water_ml"]})
        
        bot.send_message(chat_id,
            f"✅ Профиль растения настроен!\n\n"
            f"🌱 Растение: {plant}\n"
            f"📍 Регион: {region}\n"
            f"💧 Норма воды: {norms['water_ml']} мл/день\n"
            f"🌡 Оптимальная температура: {norms['temp']}°C\n"
            f"☀️ Оптимальный свет: {norms['light']}%\n"
            f"🧪 Оптимальный pH: {norms['ph']}\n\n"
            f"Теперь система будет автоматически следить за твоим растением!\n\n"
            f"📸 Можешь скинуть фото растения для анализа в любое время."
        )
    except:
        bot.send_message(chat_id, "⚠️ Ошибка настройки. Попробуй /start снова.")

# ========== СТАТУС ==========
@bot.message_handler(commands=['status'])
def status(message):
    chat_id = message.chat.id
    
    try:
        # Данные с станции
        r_station = requests.get(f"{SERVER_URL}/station/data/1/last")
        # Данные с робота  
        r_robot   = requests.get(f"{SERVER_URL}/robot/data/1/last")
        
        s = r_station.json()
        r = r_robot.json()
        
        bot.send_message(chat_id,
            f"📊 Текущие показатели:\n\n"
            f"🌡 Температура: {s.get('temp', '?')}°C\n"
            f"☀️ Свет: {s.get('light', '?')}%\n"
            f"💧 Влажность почвы: {r.get('soil_moisture', '?')}%\n"
            f"🧪 pH: {r.get('ph', '?')}\n"
        )
    except:
        bot.send_message(chat_id, "⚠️ Нет данных с датчиков")

# ========== АНАЛИЗ ФОТО ==========
@bot.message_handler(content_types=['photo'])
def analyze_photo(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "📸 Фото получено! Анализирую...")
    
    # Получаем фото
    file_id   = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    file_url  = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{
            "role": "user",
            "content": f"Пользователь прислал фото своего растения. "
                      f"У него растёт {user_profiles.get(chat_id, {}).get('plant', 'растение')}. "
                      f"Фото по ссылке: {file_url}. "
                      f"Определи проблемы растения и дай рекомендации по поливу и уходу. "
                      f"Отвечай на русском языке, коротко и понятно."
        }]
    )
    
    analysis = response.choices[0].message.content
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton(
            "💧 Разрешить полив", callback_data="allow_water"
        )
    )
    
    bot.send_message(chat_id, 
        f"🔍 Анализ растения:\n\n{analysis}",
        reply_markup=markup
    )

# ========== РАЗРЕШИТЬ ПОЛИВ ==========
@bot.callback_query_handler(func=lambda c: c.data == "allow_water")
def allow_water(call):
    chat_id = call.message.chat.id
    ml = user_profiles.get(chat_id, {}).get("norms", {}).get("water_ml", 100)
    
    requests.post(f"{SERVER_URL}/station/config/1",
                 params={"watering_ml": ml})
    
    bot.send_message(chat_id, 
        f"✅ Полив разрешён! Насос польёт {ml} мл."
    )

