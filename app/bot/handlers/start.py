from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.handlers.language import show_language_selection
from app.bot.i18n import t
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.models.enums import Language
from app.db.session import SessionLocal
from app.services.users import get_user_by_telegram_id, init_or_update_user

router = Router(name="start")


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            await show_language_selection(message, language_hint=Language.EN, include_back_to_menu=False)
            return

        user = init_or_update_user(
            db,
            telegram_id=tg_user.id,
            username=tg_user.username,
            language_code=tg_user.language_code,
        )
        if not isinstance(user.language, Language):
            await show_language_selection(message, language_hint=Language.EN, include_back_to_menu=False)
            return

    await message.answer(t("start", user.language), reply_markup=main_menu_keyboard(user.language))
