from fastapi import APIRouter, Depends, File, UploadFile, Form, Request
from sqlalchemy.orm import Session
from database import get_db, RobotData
from datetime import datetime
import os, shutil, base64
import requests as req

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Запросы на срочное фото
photo_requests = {}

# ========== ДАННЫЕ С РОБОТА ==========
@router.post("/data")
async def receive_data(
    station_id:    int   = Form(...),
    soil_moisture: float = Form(...),
    ph:            float = Form(...),
    image: UploadFile    = File(None),
    db: Session          = Depends(get_db)
):
    image_path = None
    if image and image.filename:
        filename   = f"s{station_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
        image_path = f"{UPLOAD_DIR}/{filename}"
        with open(image_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    record = RobotData(
        station_id=station_id,
        soil_moisture=soil_moisture,
        ph=ph,
        image_path=image_path
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "ok", "id": record.id}

@router.get("/data/{station_id}/last")
def get_last(station_id: int, db: Session = Depends(get_db)):
    r = db.query(RobotData).filter(
        RobotData.station_id == station_id
    ).order_by(RobotData.id.desc()).first()
    if not r:
        return {"error": "Нет данных"}
    return {
        "station_id":    r.station_id,
        "soil_moisture": r.soil_moisture,
        "ph":            r.ph,
        "image_path":    r.image_path,
        "analysis":      r.analysis,
        "created_at":    str(r.created_at)
    }

# ========== ДРОН — ЗАГРУЗКА ФОТО ==========
@router.post("/upload")
async def drone_upload(
    request: Request,
    db: Session = Depends(get_db)
):
    station_id = int(request.headers.get("X-Station-ID", 1))
    BOT_TOKEN  = os.environ.get("BOT_TOKEN")

    image_data = await request.body()
    if not image_data:
        return {"error": "Нет фото"}

    # Сохраняем фото
    filename   = f"drone_{station_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
    image_path = f"{UPLOAD_DIR}/{filename}"
    with open(image_path, "wb") as f:
        f.write(image_data)
    print(f"📸 Фото дрона: {filename}")

    # Анализ ИИ
    image_b64 = base64.b64encode(image_data).decode('utf-8')
    ai_result = analyze_with_groq(image_b64, station_id)

    # Сохраняем в базу
    record = RobotData(
        station_id=station_id,
        soil_moisture=0,
        ph=0,
        image_path=image_path,
        analysis=ai_result
    )
    db.add(record)
    db.commit()

    # Отправляем в Telegram
    send_to_telegram(BOT_TOKEN, image_data, ai_result, station_id)

    return {
        "status":   "ok",
        "analysis": ai_result,
        "image":    filename
    }

# ========== ЗАПРОС СРОЧНОГО ФОТО ==========
@router.get("/request/{station_id}")
def request_photo(station_id: int):
    photo_requests[station_id] = True
    print(f"📡 Запрос фото для станции {station_id}")
    return {"status": "requested"}

@router.get("/check/{station_id}")
def check_photo_request(station_id: int):
    needed = photo_requests.get(station_id, False)
    if needed:
        photo_requests[station_id] = False
    return {"photo_needed": needed}

# ========== ПОСЛЕДНЕЕ ФОТО ==========
@router.get("/last/{station_id}")
def get_last_photo(station_id: int, db: Session = Depends(get_db)):
    r = db.query(RobotData).filter(
        RobotData.station_id == station_id,
        RobotData.image_path != None
    ).order_by(RobotData.id.desc()).first()
    if not r:
        return {"error": "Нет фото"}
    return {
        "station_id": r.station_id,
        "image_path": r.image_path,
        "analysis":   r.analysis,
        "created_at": str(r.created_at)
    }

# ========== GROQ АНАЛИЗ ==========
def analyze_with_groq(image_b64: str, station_id: int) -> str:
    GROQ_KEY = os.environ.get("GROQ_API_KEY")
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type":  "application/json"
        }
        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Ты агроном. Это фото с дрона над полем станции {station_id}. "
                            f"Определи: "
                            f"1) Состояние растений "
                            f"2) Влажность почвы "
                            f"3) Нужен ли полив? "
                            f"Отвечай на русском, 3-4 предложения."
                        )
                    }
                ]
            }],
            "max_tokens": 300
        }
        response = req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"Groq ошибка: {response.text}")
            return "Не удалось проанализировать фото"
    except Exception as e:
        print(f"Groq исключение: {e}")
        return "Ошибка анализа"

# ========== ОТПРАВКА В TELEGRAM ==========
def send_to_telegram(bot_token: str, image_data: bytes,
                     analysis: str, station_id: int):
    try:
        chats_file = "telegram_chats.txt"
        if not os.path.exists(chats_file):
            return

        with open(chats_file, "r") as f:
            chat_ids = f.read().splitlines()

        if not chat_ids:
            return

        caption = (
            f"🚁 Фото с дрона — Станция {station_id}\n\n"
            f"🤖 Анализ ИИ:\n{analysis}"
        )

        for chat_id in chat_ids:
            try:
                req.post(
                    f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                    files={"photo": ("drone.jpg", image_data, "image/jpeg")},
                    data={"chat_id": chat_id, "caption": caption},
                    timeout=15
                )
                print(f"✅ Фото → чат {chat_id}")
            except Exception as e:
                print(f"❌ Ошибка → {chat_id}: {e}")
    except Exception as e:
        print(f"❌ Telegram ошибка: {e}")
