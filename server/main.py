from fastapi import FastAPI
from database import init_db
from routes.robot   import router as robot_router
from routes.station import router as station_router
import os

app = FastAPI(title="AgroSynapse", version="1.0.0")

app.include_router(robot_router,   prefix="/robot",   tags=["Робот"])
app.include_router(station_router, prefix="/station", tags=["Станция"])

@app.on_event("startup")
def startup():
    init_db()
    print("🌱 AgroSynapse запущен!")

@app.get("/")
def root():
    return {"status": "online", "project": "AgroSynapse"}

@app.get("/health")
def health():
    return {"status": "ok"}