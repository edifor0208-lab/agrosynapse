from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from database import get_db, StationData, StationConfig
from datetime import datetime

router = APIRouter()

@router.post("/data")
async def receive_station_data(
    station_id: int   = Form(...),
    temp:       float = Form(...),
    light:      float = Form(...),
    db: Session       = Depends(get_db)
):
    record = StationData(
        station_id=station_id,
        temp=temp,
        light=light
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "ok", "id": record.id}

@router.get("/data/{station_id}/last")
def get_last(station_id: int, db: Session = Depends(get_db)):
    r = db.query(StationData).filter(
        StationData.station_id == station_id
    ).order_by(StationData.id.desc()).first()
    if not r:
        return {"error": "Нет данных"}
    return {
        "station_id": r.station_id,
        "temp":       r.temp,
        "light":      r.light,
        "created_at": str(r.created_at)
    }

@router.get("/config/{station_id}")
def get_config(station_id: int, db: Session = Depends(get_db)):
    config = db.query(StationConfig).filter(
        StationConfig.station_id == station_id
    ).first()
    if not config:
        config = StationConfig(station_id=station_id, watering_ml=0)
        db.add(config)
        db.commit()
    return {"watering_ml": config.watering_ml}

@router.post("/config/{station_id}")
def set_config(station_id: int, watering_ml: float,
               db: Session = Depends(get_db)):
    config = db.query(StationConfig).filter(
        StationConfig.station_id == station_id
    ).first()
    if not config:
        config = StationConfig(station_id=station_id)
        db.add(config)
    config.watering_ml = watering_ml
    config.updated_at  = datetime.utcnow()
    db.commit()
    return {"status": "ok", "watering_ml": watering_ml}
