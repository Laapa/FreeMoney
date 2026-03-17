from aiogram import F, Router
from aiogram.types import Message

from app.bot.i18n import t
from app.bot.keyboards.main_menu import MENU_KEYS, main_menu_keyboard, menu_key_by_text
from app.db.session import SessionLocal
from app.services.orders import list_user_orders
from app.services.users import get_user_by_telegram_id, init_or_update_user

router = Router(name="menu")


@router.message(F.text)
async def menu_handler(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None or not message.text:
        return

    key = menu_key_by_text(message.text)
    if key not in MENU_KEYS:
        return

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

        if key == "menu_profile":
            await message.answer(
                f"{t('profile_title', user.language)}\n\n"
                + t("profile_body", user.language).format(
                    id=user.telegram_id,
                    username=f"@{user.username}" if user.username else "-",
                    language=user.language.value,
                    balance=user.balance,
                    currency=user.currency.value,
                ),
                reply_markup=main_menu_keyboard(user.language),
            )
            return

        if key == "menu_orders":
            orders = list_user_orders(db, user_id=user.id)
            if not orders:
                await message.answer(t("orders_empty", user.language), reply_markup=main_menu_keyboard(user.language))
                return

            lines = [t("orders_title", user.language)]
            for order in orders:
                lines.append(
                    f"#{order.id} | product={order.product_id} | status={order.status.value} | price={order.price}"
                )
            await message.answer("\n".join(lines), reply_markup=main_menu_keyboard(user.language))
            return

        placeholders = {
            "menu_products": "products_placeholder",
            "menu_top_up": "top_up_placeholder",
            "menu_rules": "rules_placeholder",
            "menu_support": "support_placeholder",
        }
        await message.answer(t(placeholders[key], user.language), reply_markup=main_menu_keyboard(user.language))
