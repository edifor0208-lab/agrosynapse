from fastapi import FastAPI, Request
from database import init_db
from routes.robot   import router as robot_router
from routes.station import router as station_router
import telebot
import threading

BOT_TOKEN = "8705551830:AAEzTtIvFucE_Homl61QEa6m1Uq8xDM1O1c"
bot = telebot.TeleBot(BOT_TOKEN)

app = FastAPI(title="AgroSynapse", version="1.0.0")
app.include_router(robot_router,   prefix="/robot",   tags=["Робот"])
app.include_router(station_router, prefix="/station", tags=["Станция"])

@app.on_event("startup")
def startup():
    init_db()
    # Запускаем бота в фоне
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    print("🌱 AgroSynapse запущен!")

def run_bot():
    from bot import bot
    print("🤖 Бот запущен!")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

@app.get("/")
def root():
    return {"status": "online", "project": "AgroSynapse"}

@app.get("/health")
def health():
    return {"status": "ok"}
