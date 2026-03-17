from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.i18n import t
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.db.session import SessionLocal
from app.services.users import init_or_update_user

router = Router(name="start")


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    with SessionLocal() as db:
        user = init_or_update_user(
            db,
            telegram_id=tg_user.id,
            username=tg_user.username,
            language_code=tg_user.language_code,
        )

    await message.answer(t("start", user.language), reply_markup=main_menu_keyboard(user.language))
