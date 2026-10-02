from fastapi import FastAPI

from app.config.app import APP_CONFIG
from app.errors import install_error_handlers
from app.routers import intake, ledger, notices, system

app = FastAPI(title=APP_CONFIG.name, version=APP_CONFIG.version)
install_error_handlers(app)
app.include_router(system.router)
app.include_router(intake.router)
app.include_router(ledger.router)
app.include_router(notices.router)
