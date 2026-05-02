from fastapi import FastAPI
from database import init_db
from routes.robot   import router as robot_router
from routes.station import router as station_router
import threading
import time

app = FastAPI(title="AgroSynapse", version="1.0.0")
app.include_router(robot_router,   prefix="/robot",   tags=["Робот"])
app.include_router(station_router, prefix="/station", tags=["Станция"])

@app.on_event("startup")
def startup():
    init_db()
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    print("🌱 AgroSynapse запущен!")

def run_bot():
    # Ждём 10 секунд чтобы старый бот успел остановиться
    time.sleep(10)
    try:
        import bot as telegram_bot
        print("🤖 Бот запускается!")
        telegram_bot.bot.delete_webhook()
        telegram_bot.bot.infinity_polling(
            timeout=10,
            long_polling_timeout=5,
            restart_on_change=False
        )
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")

@app.get("/")
def root():
    return {"status": "online", "project": "AgroSynapse"}

@app.get("/health")
def health():
    return {"status": "ok"}
