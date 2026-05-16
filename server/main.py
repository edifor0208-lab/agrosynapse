from fastapi import FastAPI
from database import init_db
from routes.robot   import router as robot_router
from routes.station import router as station_router
import threading
import time
import os
import requests as req

app = FastAPI(title="AgroSynapse", version="1.0.0")
app.include_router(robot_router,   prefix="/robot",   tags=["Робот"])
app.include_router(robot_router,   prefix="/drone",   tags=["Дрон"])
app.include_router(station_router, prefix="/station", tags=["Станция"])

@app.on_event("startup")
def startup():
    init_db()
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    print("🌱 AgroSynapse запущен!")

def run_bot():
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

@app.get("/test-ai")
def test_ai():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return {"error": "GEMINI_API_KEY не найден"}
    try:
        r = req.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
            json={"contents": [{"parts": [{"text": "Скажи привет"}]}]},
            timeout=10
        )
        return {"status": r.status_code, "response": r.json()}
    except Exception as e:
        return {"error": str(e)}
