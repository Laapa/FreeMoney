from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗂 Товары", callback_data="adm:products")],
            [InlineKeyboardButton(text="💵 Цены", callback_data="adm:prices")],
            [InlineKeyboardButton(text="📦 Заказы", callback_data="adm:orders")],
            [InlineKeyboardButton(text="🔑 Пул товара", callback_data="adm:stock")],
        ]
    )
