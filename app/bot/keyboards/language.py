from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import t
from app.bot.keyboards.account import CALLBACK_PROFILE_MENU
from app.models.enums import Language

CALLBACK_LANGUAGE_CHOOSE = "lang:choose"
CALLBACK_LANGUAGE_SET = "lang:set"


def language_set_callback(language: Language) -> str:
    return f"{CALLBACK_LANGUAGE_SET}:{language.value}"


def language_selection_keyboard(*, include_back_to_menu: bool, language: Language) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t("language_option_ru", language), callback_data=language_set_callback(Language.RU))],
        [InlineKeyboardButton(text=t("language_option_en", language), callback_data=language_set_callback(Language.EN))],
    ]
    if include_back_to_menu:
        rows.append([InlineKeyboardButton(text=t("nav_main_menu", language), callback_data=CALLBACK_PROFILE_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
