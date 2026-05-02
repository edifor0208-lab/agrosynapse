from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, StationConfig
from datetime import datetime

router = APIRouter()

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
def set_config(station_id: int, watering_ml: float, db: Session = Depends(get_db)):
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