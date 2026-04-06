from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.i18n import t
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.money import format_money
from app.bot.state_utils import clear_admin_state
from app.bot.keyboards.products import (
    CALLBACK_MENU,
    CALLBACK_ROOT,
    buy_offer_callback,
    categories_keyboard,
    category_callback,
    offer_callback,
    offer_card_keyboard,
    offers_keyboard,
    reservation_success_keyboard,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import FulfillmentType
from app.services.admin import is_admin_telegram_id
from app.services.catalog import get_category_view, get_offer_view, list_categories, list_offers
from app.services.purchase import create_non_stock_order_for_user, reserve_product_for_user
from app.services.users import get_user_by_telegram_id, init_or_update_user

router = Router(name="products")


def _availability_label(offer, language) -> str:
    if offer.fulfillment_type == FulfillmentType.DIRECT_STOCK:
        return str(offer.stock_count)
    if offer.fulfillment_type == FulfillmentType.ACTIVATION_TASK:
        return t("products_availability_activation", language)
    return t("products_availability_supplier", language)


async def _resolve_user(message: Message):
    tg_user = message.from_user
    if tg_user is None:
        return None
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id) or init_or_update_user(
            db,
            telegram_id=tg_user.id,
            username=tg_user.username,
            language_code=tg_user.language_code,
        )
        return user


async def show_root_categories(message: Message, state=None) -> None:
    user = await _resolve_user(message)
    if user is None:
        return
    if state is not None:
        await clear_admin_state(state)
    with SessionLocal() as db:
        categories = list_categories(db, language=user.language)
    if not categories:
        await message.answer(t("products_empty", user.language))
        return
    await message.answer(t("products_root_title", user.language), reply_markup=categories_keyboard(categories, user.language))


@router.callback_query(F.data == CALLBACK_MENU)
async def on_main_menu(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, callback.from_user.id) or init_or_update_user(
            db, telegram_id=callback.from_user.id, username=callback.from_user.username, language_code=callback.from_user.language_code
        )
    await callback.message.answer(
        t("start", user.language),
        reply_markup=main_menu_keyboard(user.language, is_admin=is_admin_telegram_id(user.telegram_id, get_settings().admin_telegram_ids)),
    )
    await callback.answer()


@router.callback_query(F.data == CALLBACK_ROOT)
async def on_root(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, callback.from_user.id) or init_or_update_user(
            db, telegram_id=callback.from_user.id, username=callback.from_user.username, language_code=callback.from_user.language_code
        )
        categories = list_categories(db, language=user.language)
    await callback.message.edit_text(t("products_root_title", user.language), reply_markup=categories_keyboard(categories, user.language))
    await callback.answer()


@router.callback_query(F.data.startswith("prod:cat:"))
async def on_category(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    category_id = int(callback.data.split(":")[-1])
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, callback.from_user.id) or init_or_update_user(
            db, telegram_id=callback.from_user.id, username=callback.from_user.username, language_code=callback.from_user.language_code
        )
        category = get_category_view(db, language=user.language, category_id=category_id)
        offers = list_offers(db, user_id=user.id, language=user.language, category_id=category_id)
    if category is None:
        await callback.answer(t("products_category_not_found", user.language), show_alert=True)
        return
    await callback.message.edit_text(
        t("products_list_title", user.language).format(title=category.title),
        reply_markup=offers_keyboard(offers=offers, category_id=category.id, language=user.language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:offer:"))
async def on_offer(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    offer_id = int(callback.data.split(":")[-1])
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, callback.from_user.id) or init_or_update_user(
            db, telegram_id=callback.from_user.id, username=callback.from_user.username, language_code=callback.from_user.language_code
        )
        offer = get_offer_view(db, user_id=user.id, language=user.language, offer_id=offer_id)
    if offer is None:
        await callback.answer(t("products_product_not_available", user.language), show_alert=True)
        return
    await callback.message.edit_text(
        t("products_offer_view", user.language).format(
            title=offer.title,
            price=format_money(offer.price) if offer.price is not None else t("products_price_missing", user.language),
            fulfillment=t(f"orders_fulfillment_{offer.fulfillment_type.value}", user.language),
            availability=_availability_label(offer, user.language),
            description=offer.description or "-",
        ),
        reply_markup=offer_card_keyboard(offer=offer, language=user.language),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:buy:"))
async def on_buy(callback: CallbackQuery) -> None:
    if callback.message is None:
        return

    offer_id = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, callback.from_user.id) or init_or_update_user(
            db,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            language_code=callback.from_user.language_code,
        )
        offer = get_offer_view(db, user_id=user.id, language=user.language, offer_id=offer_id)
        if offer is None or offer.price is None:
            await callback.answer(t("products_product_not_available", user.language), show_alert=True)
            return

        if offer.fulfillment_type == FulfillmentType.DIRECT_STOCK:
            attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=offer.price)
            if not attempt.ok or attempt.order is None:
                await callback.answer(t("products_no_stock", user.language), show_alert=True)
                return

            reservation_id = attempt.reservation.id if attempt.reservation else "-"
            order_id = attempt.order.id
            order_price = attempt.order.price

        else:
            attempt = create_non_stock_order_for_user(
                db,
                user_id=user.id,
                offer_id=offer.id,
                price=offer.price,
                fulfillment_type=offer.fulfillment_type,
            )
            if not attempt.ok or attempt.order is None:
                await callback.answer(t("products_no_stock", user.language), show_alert=True)
                return

            reservation_id = "-"
            order_id = attempt.order.id
            order_price = attempt.order.price

    if offer.fulfillment_type == FulfillmentType.DIRECT_STOCK:
        success_text = t("products_reservation_success", user.language).format(
            title=offer.title,
            reservation_id=reservation_id,
            order_id=order_id,
            price=format_money(order_price),
            ttl_minutes=get_settings().product_reservation_ttl_minutes,
        )
    else:
        success_text = t("products_order_created_success", user.language).format(
            title=offer.title,
            order_id=order_id,
            price=format_money(order_price),
        )

    await callback.message.edit_text(
        success_text,
        reply_markup=reservation_success_keyboard(category_id=offer.category_id, language=user.language),
    )
    await callback.answer(t("products_reserved_toast", user.language))
