from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import t
from app.models.enums import Language
from app.services.catalog import CategoryView, OfferView

CALLBACK_ROOT = "prod:root"
CALLBACK_MENU = "prod:menu"


def category_callback(category_id: int) -> str:
    return f"prod:cat:{category_id}"


def offer_callback(offer_id: int) -> str:
    return f"prod:offer:{offer_id}"


def buy_offer_callback(offer_id: int) -> str:
    return f"prod:buy:{offer_id}"


def open_product_callback(offer_id: int, product_id: int) -> str:
    return f"prod:item:{offer_id}:{product_id}"


def buy_product_callback(offer_id: int, product_id: int) -> str:
    return f"prod:itembuy:{offer_id}:{product_id}"


def categories_keyboard(categories: list[CategoryView], language: Language) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"📁 {c.title}", callback_data=category_callback(c.id))] for c in categories]
    rows.append([InlineKeyboardButton(text=t("products_main_menu", language), callback_data=CALLBACK_MENU)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offers_keyboard(*, offers: list[OfferView], category_id: int, language: Language) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"🛍 {o.title}", callback_data=offer_callback(o.id))] for o in offers]
    rows.append([
        InlineKeyboardButton(text=t("products_back", language), callback_data=CALLBACK_ROOT),
        InlineKeyboardButton(text=t("products_main_menu", language), callback_data=CALLBACK_MENU),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offer_card_keyboard(*, offer: OfferView, language: Language) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if offer.fulfillment_type == "direct_stock":
        pass
    rows.append([InlineKeyboardButton(text=t("products_buy", language), callback_data=buy_offer_callback(offer.id))])
    rows.append([
        InlineKeyboardButton(text=t("products_back_to_category", language), callback_data=category_callback(offer.category_id)),
        InlineKeyboardButton(text=t("products_main_menu", language), callback_data=CALLBACK_MENU),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_card_keyboard(*, offer_id: int, product_id: int, language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("products_buy", language), callback_data=buy_product_callback(offer_id, product_id))],
            [InlineKeyboardButton(text=t("products_back_to_products", language), callback_data=offer_callback(offer_id))],
        ]
    )


def reservation_success_keyboard(*, category_id: int, language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("products_back", language), callback_data=category_callback(category_id))]])
