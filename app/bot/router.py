from aiogram import Dispatcher

from app.bot.handlers.language import router as language_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.products import router as products_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.top_up import router as top_up_router


def setup_routers(dp: Dispatcher) -> None:
    dp.include_router(start_router)
    dp.include_router(language_router)
    dp.include_router(products_router)
    dp.include_router(top_up_router)
    dp.include_router(menu_router)
