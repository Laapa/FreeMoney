from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import t
from app.models.enums import Language
from app.models.order import Order

CALLBACK_PROFILE_BACK = "acc:profile:back"
CALLBACK_PROFILE_MENU = "acc:profile:menu"
CALLBACK_PROFILE_LANGUAGE = "acc:profile:language"
CALLBACK_ORDERS_BACK = "acc:orders:back"
CALLBACK_ORDERS_MENU = "acc:orders:menu"
CALLBACK_ORDERS_PAGE = "acc:orders:page"
CALLBACK_ORDERS_OPEN = "acc:orders:open"
CALLBACK_ORDERS_PAY = "acc:orders:pay"
CALLBACK_ORDERS_CHECK_PAYMENT = "acc:orders:check"
CALLBACK_ORDERS_CANCEL_PAYMENT = "acc:orders:cancel"
CALLBACK_ORDERS_TOP_UP = "acc:orders:topup"


def orders_page_callback(page: int) -> str:
    return f"{CALLBACK_ORDERS_PAGE}:{page}"


def order_open_callback(order_id: int) -> str:
    return f"{CALLBACK_ORDERS_OPEN}:{order_id}"


def order_pay_callback(order_id: int) -> str:
    return f"{CALLBACK_ORDERS_PAY}:{order_id}"


def order_check_payment_callback(order_id: int) -> str:
    return f"{CALLBACK_ORDERS_CHECK_PAYMENT}:{order_id}"


def order_cancel_payment_callback(order_id: int) -> str:
    return f"{CALLBACK_ORDERS_CANCEL_PAYMENT}:{order_id}"


def profile_keyboard(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("profile_change_language", language), callback_data=CALLBACK_PROFILE_LANGUAGE)],
            [InlineKeyboardButton(text=t("nav_back", language), callback_data=CALLBACK_PROFILE_BACK)],
            [InlineKeyboardButton(text=t("nav_main_menu", language), callback_data=CALLBACK_PROFILE_MENU)],
        ]
    )


def orders_keyboard(*, language: Language, page: int, pages: int, orders: list[Order]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for order in orders:
        rows.append([InlineKeyboardButton(text=t("orders_open", language).format(id=order.id), callback_data=order_open_callback(order.id))])

    if pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text=t("nav_prev", language), callback_data=orders_page_callback(page - 1)))
        if page < pages:
            nav_row.append(InlineKeyboardButton(text=t("nav_next", language), callback_data=orders_page_callback(page + 1)))
        if nav_row:
            rows.append(nav_row)

    rows.append([InlineKeyboardButton(text=t("nav_back", language), callback_data=CALLBACK_ORDERS_BACK)])
    rows.append([InlineKeyboardButton(text=t("nav_main_menu", language), callback_data=CALLBACK_ORDERS_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_details_keyboard(
    *,
    language: Language,
    order_id: int,
    can_pay: bool,
    show_top_up: bool,
    payment_url: str | None = None,
    payment_screen: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_pay and not payment_screen:
        rows.append([InlineKeyboardButton(text=t("orders_action_pay", language), callback_data=order_pay_callback(order_id))])
    if payment_url:
        rows.append([InlineKeyboardButton(text=t("orders_action_open_payment", language), url=payment_url)])
    if can_pay or payment_screen:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("orders_action_check_payment", language),
                    callback_data=order_check_payment_callback(order_id),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("orders_action_cancel_payment", language),
                    callback_data=order_cancel_payment_callback(order_id),
                )
            ]
        )
    if show_top_up:
        rows.append([InlineKeyboardButton(text=t("orders_action_top_up", language), callback_data=CALLBACK_ORDERS_TOP_UP)])
    rows.append([InlineKeyboardButton(text=t("nav_back", language), callback_data=CALLBACK_ORDERS_BACK)])
    rows.append([InlineKeyboardButton(text=t("nav_main_menu", language), callback_data=CALLBACK_ORDERS_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
