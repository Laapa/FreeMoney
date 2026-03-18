from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.web.routes.activation import router as activation_router

configure_logging()
settings = get_settings()
app = FastAPI(title=settings.app_name)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.include_router(activation_router, prefix="/activation")


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse(url="/activation", status_code=302)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@app.get("/health/ready", tags=["health"])
def readiness_check() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
