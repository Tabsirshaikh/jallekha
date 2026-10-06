from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.api import ApiConfig
from app.config.app import APP_CONFIG
from app.errors import install_error_handlers
from app.routers import (
    auth_routes,
    contests,
    debt,
    deliveries,
    evidence,
    forecast,
    intake,
    ledger,
    notices,
    plans,
    section_outcomes,
    stops,
    system,
)

load_dotenv()

app = FastAPI(title=APP_CONFIG.name, version=APP_CONFIG.version)
install_error_handlers(app)
# CORS for the frontend (T10): origins from CORS_ORIGINS, default the Vite dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ApiConfig.from_env().cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Gateway-Token"],
)
app.include_router(system.router)
app.include_router(auth_routes.router)
app.include_router(intake.router)
app.include_router(ledger.router)
app.include_router(notices.router)
app.include_router(evidence.router)
app.include_router(forecast.router)
app.include_router(plans.router)
app.include_router(contests.router)
app.include_router(deliveries.router)
app.include_router(stops.router)
app.include_router(debt.router)
app.include_router(section_outcomes.router)
