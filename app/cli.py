import uvicorn

from app.bot.main import main as run_bot_main
from app.scripts.seed_demo_data import main as seed_demo_data_main


def run_api() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


def run_bot() -> None:
    run_bot_main()


def seed_demo() -> None:
    seed_demo_data_main()
