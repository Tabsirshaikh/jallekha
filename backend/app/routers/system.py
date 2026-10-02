from fastapi import APIRouter

from app.config.app import APP_CONFIG

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a dependency-free readiness signal for local and CI checks."""
    return {"status": "ok", "service": APP_CONFIG.name, "version": APP_CONFIG.version}
