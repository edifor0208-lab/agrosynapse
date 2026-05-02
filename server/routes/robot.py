from fastapi import APIRouter, Depends, File, UploadFile, Form
from sqlalchemy.orm import Session
from database import get_db, SensorData
from datetime import datetime
import os, shutil

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/data")
async def receive_data(
    station_id:    int   = Form(...),
    soil_moisture: float = Form(...),
    ph:            float = Form(...),
    temp:          float = Form(...),
    image: UploadFile    = File(None),
    db: Session          = Depends(get_db)
):
    image_path = None
    if image and image.filename:
        filename   = f"s{station_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
        image_path = f"{UPLOAD_DIR}/{filename}"
        with open(image_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    record = SensorData(
        station_id=station_id, soil_moisture=soil_moisture,
        ph=ph, temp=temp, image_path=image_path
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    print(f"📊 Станция {station_id}: влажность={soil_moisture}% pH={ph} temp={temp}°C")
    return {"status": "ok", "id": record.id}

@router.get("/data/{station_id}/last")
def get_last(station_id: int, db: Session = Depends(get_db)):
    r = db.query(SensorData).filter(
        SensorData.station_id == station_id
    ).order_by(SensorData.id.desc()).first()
    if not r:
        return {"error": "Нет данных"}
    return {"station_id": r.station_id, "soil_moisture": r.soil_moisture,
            "ph": r.ph, "temp": r.temp, "created_at": r.created_at}