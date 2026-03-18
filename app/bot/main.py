import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.bot.router import setup_routers
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


async def run_polling() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run bot polling")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    setup_routers(dispatcher)
    logger.info("Starting Telegram bot polling")
    await dispatcher.start_polling(bot)


def main() -> None:
    configure_logging()
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
