from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Категории", callback_data="adm:products")],
            [InlineKeyboardButton(text="Офферы и цены", callback_data="adm:prices")],
            [InlineKeyboardButton(text="Заказы", callback_data="adm:orders")],
            [InlineKeyboardButton(text="Пул товара", callback_data="adm:stock")],
            [InlineKeyboardButton(text="Выйти из админки", callback_data="adm:exit")],
        ]
    )
