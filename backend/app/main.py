from fastapi import FastAPI

from app.config.app import APP_CONFIG
from app.routers import system

app = FastAPI(title=APP_CONFIG.name, version=APP_CONFIG.version)
app.include_router(system.router)
