from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.web.routes.activation import router as activation_router

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.include_router(activation_router, prefix="/activation")


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse(url="/activation", status_code=302)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
