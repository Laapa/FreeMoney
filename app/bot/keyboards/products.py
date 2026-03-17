from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import t
from app.models.enums import Language
from app.services.catalog import CategoryView


CALLBACK_ROOT = "prod:root"


def category_callback(category_id: int) -> str:
    return f"prod:cat:{category_id}"


def products_callback(category_id: int) -> str:
    return f"prod:list:{category_id}"


def buy_callback(category_id: int) -> str:
    return f"prod:buy:{category_id}"


def back_callback(parent_id: int | None) -> str:
    if parent_id is None:
        return CALLBACK_ROOT
    return category_callback(parent_id)


def categories_keyboard(categories: list[CategoryView], language: Language) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for category in categories:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{category.title} ({category.stock_count})",
                    callback_data=category_callback(category.id),
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_view_keyboard(
    *,
    category: CategoryView,
    subcategories: list[CategoryView],
    language: Language,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for subcategory in subcategories:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{subcategory.title} ({subcategory.stock_count})",
                    callback_data=category_callback(subcategory.id),
                )
            ]
        )

    rows.append([InlineKeyboardButton(text=t("products_open_list", language), callback_data=products_callback(category.id))])
    rows.append([InlineKeyboardButton(text=t("products_back", language), callback_data=back_callback(category.parent_id))])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_list_keyboard(*, category: CategoryView, can_buy: bool, language: Language) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_buy:
        rows.append([InlineKeyboardButton(text=t("products_buy", language), callback_data=buy_callback(category.id))])

    rows.append([InlineKeyboardButton(text=t("products_back", language), callback_data=category_callback(category.id))])

    return InlineKeyboardMarkup(inline_keyboard=rows)
