from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./agrosynapse.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class SensorData(Base):
    __tablename__ = "sensor_data"
    id            = Column(Integer, primary_key=True, index=True)
    station_id    = Column(Integer)
    soil_moisture = Column(Float)
    ph            = Column(Float)
    temp          = Column(Float)
    image_path    = Column(String, nullable=True)
    light         = Column(Float, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

class StationConfig(Base):
    __tablename__ = "station_config"
    id          = Column(Integer, primary_key=True, index=True)
    station_id  = Column(Integer, unique=True)
    watering_ml = Column(Float, default=0)
    updated_at  = Column(DateTime, default=datetime.utcnow)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ База данных готова")
