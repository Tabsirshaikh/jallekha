from fastapi import FastAPI

from app.config.app import APP_CONFIG

app = FastAPI(title=APP_CONFIG.name, version=APP_CONFIG.version)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return a dependency-free readiness signal for local and CI checks."""
    return {"status": "ok", "service": APP_CONFIG.name, "version": APP_CONFIG.version}
