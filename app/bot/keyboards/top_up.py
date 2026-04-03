from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.bot.i18n import t
from app.models.enums import Language

TOP_UP_METHOD_CRYPTO = "top_up_method_crypto"
TOP_UP_METHOD_BYBIT = "top_up_method_bybit"
TOP_UP_MY_REQUESTS = "top_up_my_requests"
TOP_UP_CANCEL = "top_up_cancel"


def top_up_main_keyboard(language: Language, *, show_bybit: bool = True) -> ReplyKeyboardMarkup:
    return top_up_main_keyboard_for_request(language, show_bybit=show_bybit)


def top_up_main_keyboard_for_request(
    language: Language,
    *,
    show_bybit: bool = True,
    bybit_retry_request_id: int | None = None,
) -> ReplyKeyboardMarkup:
    method_row = [KeyboardButton(text=t(TOP_UP_METHOD_CRYPTO, language))]
    if show_bybit:
        method_row.append(KeyboardButton(text=t(TOP_UP_METHOD_BYBIT, language)))
    request_rows = [[KeyboardButton(text=t(TOP_UP_MY_REQUESTS, language))]]
    if bybit_retry_request_id is not None:
        request_rows.append([KeyboardButton(text=t("top_up_bybit_retry_button", language).format(id=bybit_retry_request_id))])
    return ReplyKeyboardMarkup(
        keyboard=[
            method_row,
            *request_rows,
            [KeyboardButton(text=t("nav_back", language)), KeyboardButton(text=t("nav_main_menu", language))],
        ],
        resize_keyboard=True,
    )


def top_up_cancel_keyboard(language: Language) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(TOP_UP_CANCEL, language))],
            [KeyboardButton(text=t("nav_back", language)), KeyboardButton(text=t("nav_main_menu", language))],
        ],
        resize_keyboard=True,
    )


def top_up_network_keyboard(language: Language, *, network_labels: list[str]) -> ReplyKeyboardMarkup:
    network_rows = [[KeyboardButton(text=label)] for label in network_labels]
    return ReplyKeyboardMarkup(
        keyboard=[
            *network_rows,
            [KeyboardButton(text=t(TOP_UP_CANCEL, language))],
            [KeyboardButton(text=t("nav_back", language)), KeyboardButton(text=t("nav_main_menu", language))],
        ],
        resize_keyboard=True,
    )
