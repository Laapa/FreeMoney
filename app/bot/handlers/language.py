from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.i18n import t
from app.bot.keyboards.account import CALLBACK_PROFILE_LANGUAGE
from app.bot.keyboards.language import CALLBACK_LANGUAGE_SET, language_selection_keyboard
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.db.session import SessionLocal
from app.models.enums import Language
from app.services.users import get_user_by_telegram_id, init_or_update_user, set_user_language

router = Router(name="language")


async def show_language_selection(
    message: Message,
    *,
    language_hint: Language | None,
    include_back_to_menu: bool,
) -> None:
    ui_language = language_hint or Language.EN
    await message.answer(
        t("language_prompt", ui_language),
        reply_markup=language_selection_keyboard(include_back_to_menu=include_back_to_menu, language=ui_language),
    )


@router.callback_query(F.data == CALLBACK_PROFILE_LANGUAGE)
async def on_profile_language(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, callback.from_user.id)

    await show_language_selection(
        message,
        language_hint=user.language if user is not None else Language.EN,
        include_back_to_menu=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_LANGUAGE_SET}:"))
async def on_language_selected(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None or callback.data is None:
        await callback.answer()
        return

    raw_language = callback.data.split(":")[-1]
    try:
        selected_language = Language(raw_language)
    except ValueError:
        await callback.answer()
        return

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, callback.from_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                language_code=selected_language.value,
            )
        user = set_user_language(db, user=user, language=selected_language)

    await message.answer(t("language_saved", selected_language))
    await message.answer(t("start", selected_language), reply_markup=main_menu_keyboard(selected_language))
    await callback.answer()
