from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.i18n import t
from app.models.enums import Language

MENU_KEYS = ["menu_products", "menu_top_up", "menu_profile", "menu_orders", "menu_rules", "menu_support"]


def main_menu_keyboard(language: Language) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("menu_products", language)), KeyboardButton(text=t("menu_top_up", language))],
            [KeyboardButton(text=t("menu_profile", language)), KeyboardButton(text=t("menu_orders", language))],
            [KeyboardButton(text=t("menu_rules", language)), KeyboardButton(text=t("menu_support", language))],
        ],
        resize_keyboard=True,
    )


def menu_key_by_text(text: str) -> str | None:
    for key in MENU_KEYS:
        if text in {t(key, Language.RU), t(key, Language.EN)}:
            return key
    return None
