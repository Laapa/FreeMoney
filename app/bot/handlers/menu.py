from math import ceil
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.handlers.products import show_root_categories
from app.bot.i18n import t
from app.bot.money import format_money
from app.bot.state_utils import clear_admin_state
from app.bot.keyboards.account import (
    CALLBACK_ORDERS_BACK,
    CALLBACK_ORDERS_MENU,
    CALLBACK_ORDERS_CANCEL_PAYMENT,
    CALLBACK_ORDERS_CHECK_PAYMENT,
    CALLBACK_ORDERS_OPEN,
    CALLBACK_ORDERS_PAGE,
    CALLBACK_ORDERS_PAY,
    CALLBACK_ORDERS_PAY_BALANCE,
    CALLBACK_ORDERS_TOP_UP,
    CALLBACK_PROFILE_BACK,
    CALLBACK_PROFILE_MENU,
    order_details_keyboard,
    orders_keyboard,
    profile_keyboard,
)
from app.bot.keyboards.main_menu import MENU_KEYS, main_menu_keyboard, menu_key_by_text
from app.bot.keyboards.top_up import top_up_main_keyboard
from app.db.session import SessionLocal
from app.core.config import get_settings
from app.models.offer import Offer
from app.models.enums import FulfillmentType, Language, OrderStatus, PaymentMethod
from app.models.order import Order
from app.models.user import User
from app.bot.handlers.top_up import TopUpStates
from app.services.orders import count_user_orders, get_user_order, get_user_order_stats, list_user_orders, pay_pending_order_from_balance
from app.services.payments import cancel_order_payment, check_order_payment, create_order_payment
from app.services.users import get_user_by_telegram_id, init_or_update_user
from app.services.admin import is_admin_telegram_id

router = Router(name="menu")
ORDERS_PER_PAGE = 5
logger = logging.getLogger(__name__)


def _format_dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _order_status_label(status: OrderStatus, language: Language) -> str:
    return t(f"orders_status_{status.value}", language)


def _payment_method_for_new_invoice() -> PaymentMethod:
    settings = get_settings()
    return PaymentMethod.CRYPTO_PAY if settings.cryptopay_api_token else PaymentMethod.TEST_STUB


def _activation_link_for_order(order: Order) -> str | None:
    if order.fulfillment_type != FulfillmentType.ACTIVATION_TASK:
        return None
    return get_settings().activation_public_url



def _is_bybit_available_for_top_up() -> bool:
    settings = get_settings()
    return settings.bybit_enabled and bool((settings.bybit_recipient_uid or "").strip())


def _payment_method_label(method: PaymentMethod, language: Language) -> str:
    if method == PaymentMethod.CRYPTO_PAY:
        return "Crypto Pay"
    if method == PaymentMethod.TEST_STUB:
        return "Test Stub"
    return method.value


async def _notify_admins_manual_order(*, callback: CallbackQuery, order: Order, offer: Offer | None, user: User) -> None:
    if order.fulfillment_type not in {FulfillmentType.MANUAL_SUPPLIER, FulfillmentType.ACTIVATION_TASK}:
        return
    offer_name = offer.name_ru if (offer and user.language == Language.RU) else (offer.name_en if offer else f"offer#{order.offer_id}")
    username_label = f"@{user.username}" if user.username else "-"
    text = (
        "⚠️ Заказ требует ручной обработки\n"
        f"order_id: {order.id}\n"
        f"user_telegram_id: {user.telegram_id}\n"
        f"username: {username_label}"
    )
    text += (
        f"\noffer: {offer_name}\n"
        f"fulfillment_type: {order.fulfillment_type.value}\n"
        f"amount: {format_money(order.price)}\n"
        f"status: {order.status.value}"
    )
    for admin_id in get_settings().admin_telegram_ids:
        try:
            await callback.bot.send_message(chat_id=admin_id, text=text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to notify admin about manual order | order_id=%s admin_id=%s err=%s", order.id, admin_id, str(exc))


def _sanitize_payload(payload: str, limit: int = 300) -> str:
    safe_payload = payload.strip()
    if len(safe_payload) <= limit:
        return safe_payload
    return f"{safe_payload[:limit]}..."


def _render_orders_text(
    *,
    language: Language,
    orders: list[Order],
    page: int,
    pages: int,
    order_item_titles: dict[int, str] | None = None,
) -> str:
    lines = [t("orders_title", language).format(page=page, pages=pages), ""]

    for order in orders:
        lines.append(
            t("orders_card", language).format(
                id=order.id,
                created_at=_format_dt(order.created_at),
                status=_order_status_label(order.status, language),
                price=format_money(order.price),
            )
        )
        item_title = (order_item_titles or {}).get(order.id)
        if item_title:
            lines.append(t("orders_item_line", language).format(item=item_title))
        if order.status == OrderStatus.DELIVERED and order.delivered_payload:
            lines.append(t("orders_payload", language).format(payload=_sanitize_payload(order.delivered_payload)))
        lines.append("")

    return "\n".join(lines).strip()


def _render_order_details_text(*, language: Language, order: Order, item_title: str | None = None) -> str:
    lines = [
        t("orders_details_title", language).format(id=order.id),
        t("orders_details_created", language).format(created_at=_format_dt(order.created_at)),
        t("orders_details_status", language).format(status=_order_status_label(order.status, language)),
        t("orders_details_price", language).format(price=format_money(order.price)),
    ]
    if item_title:
        lines.append(t("orders_item_line", language).format(item=item_title))
    if order.status == OrderStatus.DELIVERED and order.delivered_payload:
        lines.append(t("orders_payload", language).format(payload=_sanitize_payload(order.delivered_payload)))
    if order.delivered_at is not None:
        lines.append(t("orders_details_delivered_at", language).format(delivered_at=_format_dt(order.delivered_at)))
    return "\n".join(lines)


def _resolve_or_create_user(tg_user) -> User:
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, tg_user.id)
        if user is None:
            user = init_or_update_user(
                db,
                telegram_id=tg_user.id,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )
        return user


def _main_menu_for_user(user: User) -> object:
    is_admin = is_admin_telegram_id(user.telegram_id, get_settings().admin_telegram_ids)
    return main_menu_keyboard(user.language, is_admin=is_admin)


async def _show_profile(message: Message, user: User) -> None:
    with SessionLocal() as db:
        stats = get_user_order_stats(db, user_id=user.id)

    await message.answer(
        f"{t('profile_title', user.language)}\n\n"
        + t("profile_body", user.language).format(
            id=user.telegram_id,
            username=f"@{user.username}" if user.username else "-",
            registered_at=_format_dt(user.created_at),
            language=user.language.value,
            balance=format_money(user.balance),
            total_orders=stats.total_orders,
            delivered_orders=stats.delivered_orders,
            total_spent=format_money(stats.total_spent),
        ),
        reply_markup=profile_keyboard(user.language),
    )


async def _show_orders(message: Message, user: User, page: int = 1) -> None:
    with SessionLocal() as db:
        total = count_user_orders(db, user_id=user.id)
        if total == 0:
            await message.answer(t("orders_empty", user.language), reply_markup=_main_menu_for_user(user))
            return

        pages = ceil(total / ORDERS_PER_PAGE)
        page = max(1, min(page, pages))
        orders = list_user_orders(db, user_id=user.id, limit=ORDERS_PER_PAGE, offset=(page - 1) * ORDERS_PER_PAGE)
        offer_ids = {order.offer_id for order in orders}
        offers = db.scalars(select(Offer).where(Offer.id.in_(offer_ids))).all() if offer_ids else []
        offer_titles = {offer.id: offer.name_ru if user.language == Language.RU else offer.name_en for offer in offers}
        order_item_titles = {order.id: offer_titles.get(order.offer_id, f"Offer #{order.offer_id}") for order in orders}

    await message.answer(
        _render_orders_text(
            language=user.language,
            orders=orders,
            page=page,
            pages=pages,
            order_item_titles=order_item_titles,
        ),
        reply_markup=orders_keyboard(language=user.language, page=page, pages=pages, orders=orders),
    )


@router.message(F.text)
async def menu_handler(message: Message, state: FSMContext) -> None:
    tg_user = message.from_user
    if tg_user is None or not message.text:
        return
    if message.text.startswith("/"):
        return

    key = menu_key_by_text(message.text)
    if key not in MENU_KEYS:
        return

    user = _resolve_or_create_user(tg_user)
    if key in {"menu_products", "menu_top_up", "menu_profile", "menu_orders", "menu_rules", "menu_support"}:
        await clear_admin_state(state)

    if key == "menu_profile":
        await _show_profile(message, user)
        return

    if key == "menu_orders":
        await _show_orders(message, user, page=1)
        return

    if key == "menu_products":
        await show_root_categories(message, state=state)
        return

    placeholders = {
        "menu_rules": "rules_placeholder",
        "menu_support": "support_placeholder",
    }
    if key == "menu_admin":
        await message.answer("Откройте /admin", reply_markup=_main_menu_for_user(user))
        return
    if key == "menu_top_up":
        return
    await message.answer(t(placeholders[key], user.language), reply_markup=_main_menu_for_user(user))


@router.callback_query(F.data.in_({CALLBACK_PROFILE_BACK, CALLBACK_PROFILE_MENU, CALLBACK_ORDERS_BACK, CALLBACK_ORDERS_MENU}))
async def on_menu_return(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    await message.answer(t("start", user.language), reply_markup=_main_menu_for_user(user))
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_ORDERS_PAGE}:"))
async def on_orders_page(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None or callback.data is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    page = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        total = count_user_orders(db, user_id=user.id)
        if total == 0:
            await message.answer(t("orders_empty", user.language), reply_markup=_main_menu_for_user(user))
            await callback.answer()
            return

        pages = ceil(total / ORDERS_PER_PAGE)
        page = max(1, min(page, pages))
        orders = list_user_orders(db, user_id=user.id, limit=ORDERS_PER_PAGE, offset=(page - 1) * ORDERS_PER_PAGE)
        offer_ids = {order.offer_id for order in orders}
        offers = db.scalars(select(Offer).where(Offer.id.in_(offer_ids))).all() if offer_ids else []
        offer_titles = {offer.id: offer.name_ru if user.language == Language.RU else offer.name_en for offer in offers}
        order_item_titles = {order.id: offer_titles.get(order.offer_id, f"Offer #{order.offer_id}") for order in orders}

    await message.edit_text(
        _render_orders_text(
            language=user.language,
            orders=orders,
            page=page,
            pages=pages,
            order_item_titles=order_item_titles,
        ),
        reply_markup=orders_keyboard(language=user.language, page=page, pages=pages, orders=orders),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_ORDERS_OPEN}:"))
async def on_order_open(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None or callback.data is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    order_id = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        order = get_user_order(db, user_id=user.id, order_id=order_id)
        if order is None:
            await callback.answer(t("orders_not_found", user.language), show_alert=True)
            return
        item_title = None
        offer = db.get(Offer, order.offer_id)
        if offer is not None:
            item_title = offer.name_ru if user.language == Language.RU else offer.name_en

    await message.edit_text(
        _render_order_details_text(language=user.language, order=order, item_title=item_title),
        reply_markup=order_details_keyboard(
            language=user.language,
            order_id=order.id,
            can_pay=order.status == OrderStatus.PENDING,
            can_pay_balance=order.status == OrderStatus.PENDING and user.balance >= order.price,
            show_top_up=order.status == OrderStatus.PENDING,
            activation_url=_activation_link_for_order(order),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_ORDERS_PAY}:"))
async def on_order_pay(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None or callback.data is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    order_id = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        order = get_user_order(db, user_id=user.id, order_id=order_id)
        if order is None:
            await callback.answer(t("orders_not_found", user.language), show_alert=True)
            return

        payment_result = create_order_payment(
            db,
            order=order,
            method=_payment_method_for_new_invoice(),
        )

        order = get_user_order(db, user_id=user.id, order_id=order_id)
        item_title = None
        if order:
            offer = db.get(Offer, order.offer_id)
            if offer is not None:
                item_title = offer.name_ru if user.language == Language.RU else offer.name_en

        payment = payment_result.payment

    if not payment_result.ok:
        await message.edit_text(
            f"{t('orders_payment_not_available', user.language)}\nreason={payment_result.reason}",
            reply_markup=order_details_keyboard(
                language=user.language,
                order_id=order_id,
                can_pay=False,
                can_pay_balance=False,
                show_top_up=False,
            ),
        )
        await callback.answer()
        return

    payment_url = None
    payment_method_label = "-"
    payment_deadline = "-"

    if payment is not None:
        payment_url = payment.provider_payment_url or payment.provider_invoice_url
        payment_method_label = _payment_method_label(payment.method, user.language)
        payment_deadline = _format_dt(payment.expires_at) if payment.expires_at else "-"

    await message.edit_text(
        t("orders_payment_screen", user.language).format(
            id=order.id,
            title=item_title
            or (f"#{order.product_id}" if order.product_id else t(f"orders_fulfillment_{order.fulfillment_type.value}", user.language)),
            amount=format_money(payment.net_amount if payment else order.price),
            fee_amount=format_money(payment.fee_amount if payment else 0),
            gross_amount=format_money(payment.gross_amount if payment else order.price),
            method=payment_method_label,
            created_at=_format_dt(order.created_at),
            deadline=payment_deadline,
        )
        + "\n\n"
        + t("orders_bybit_via_balance_hint", user.language),
        reply_markup=order_details_keyboard(
            language=user.language,
            order_id=order.id,
            can_pay=False,
            can_pay_balance=False,
            show_top_up=True,
            payment_url=payment_url,
            payment_screen=True,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_ORDERS_CHECK_PAYMENT}:"))
async def on_order_check_payment(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None or callback.data is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    order_id = int(callback.data.split(":")[-1])
    with SessionLocal() as db:
        order = get_user_order(db, user_id=user.id, order_id=order_id)
        if order is None:
            await callback.answer(t("orders_not_found", user.language), show_alert=True)
            return
        old_status = order.status
        result = check_order_payment(db, order=order, test_confirm=True)
        order = get_user_order(db, user_id=user.id, order_id=order_id)
        item_title = None
        order_offer = None
        if order:
            order_offer = db.get(Offer, order.offer_id)
            if order_offer is not None:
                item_title = order_offer.name_ru if user.language == Language.RU else order_offer.name_en

    if order is None:
        await callback.answer(t("orders_not_found", user.language), show_alert=True)
        return
    if not result.ok:
        if result.reason in {"payment_pending"}:
            message_key = "orders_payment_pending"
        elif result.reason in {"payment_expired", "invoice_expired"}:
            message_key = "orders_payment_expired"
        elif result.reason in {"invoice_not_found", "invoice_invalid", "invoice_missing"}:
            message_key = "orders_payment_invalid"
        elif result.reason in {"cryptopay_unavailable", "cryptopay_not_configured"}:
            message_key = "orders_payment_unavailable"
        else:
            message_key = "orders_payment_pending"
        await callback.answer(t(message_key, user.language), show_alert=True)
        return

    await message.edit_text(
        t("orders_payment_success", user.language)
        + "\n\n"
        + _render_order_details_text(language=user.language, order=order, item_title=item_title),
        reply_markup=order_details_keyboard(
            language=user.language,
            order_id=order.id,
            can_pay=False,
            can_pay_balance=False,
            show_top_up=False,
            activation_url=_activation_link_for_order(order),
        ),
    )
    if order.delivered_payload:
        await message.answer(t("orders_delivery_message", user.language).format(payload=order.delivered_payload))
    elif old_status == OrderStatus.PENDING and order.status == OrderStatus.PROCESSING:
        await _notify_admins_manual_order(callback=callback, order=order, offer=order_offer, user=user)
    await callback.answer(t("orders_payment_success_toast", user.language))


@router.callback_query(F.data.startswith(f"{CALLBACK_ORDERS_CANCEL_PAYMENT}:"))
async def on_order_cancel_payment(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None or callback.data is None:
        await callback.answer()
        return
    user = _resolve_or_create_user(callback.from_user)
    order_id = int(callback.data.split(":")[-1])
    with SessionLocal() as db:
        order = get_user_order(db, user_id=user.id, order_id=order_id)
        if order is None:
            await callback.answer(t("orders_not_found", user.language), show_alert=True)
            return
        result = cancel_order_payment(db, order=order)
    if not result.ok:
        await callback.answer(t("orders_payment_not_available", user.language), show_alert=True)
        return
    await message.edit_text(t("orders_payment_canceled", user.language), reply_markup=order_details_keyboard(language=user.language, order_id=order_id, can_pay=False, can_pay_balance=False, show_top_up=False))
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_ORDERS_PAY_BALANCE}:"))
async def on_order_pay_balance(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None or callback.data is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    order_id = int(callback.data.split(":")[-1])

    with SessionLocal() as db:
        order_before = get_user_order(db, user_id=user.id, order_id=order_id)
        result = pay_pending_order_from_balance(db, user_id=user.id, order_id=order_id)
        order = get_user_order(db, user_id=user.id, order_id=order_id)
        if order is not None:
            offer = db.get(Offer, order.offer_id)
            item_title = offer.name_ru if (offer and user.language == Language.RU) else (offer.name_en if offer else None)
        else:
            item_title = None

    if not result.ok:
        await callback.answer(t("orders_payment_insufficient_balance", user.language).format(balance=format_money(user.balance)), show_alert=True)
        return

    if order is None:
        await callback.answer(t("orders_not_found", user.language), show_alert=True)
        return

    await message.edit_text(
        t("orders_payment_success", user.language) + "\n\n" + _render_order_details_text(language=user.language, order=order, item_title=item_title),
        reply_markup=order_details_keyboard(language=user.language, order_id=order.id, can_pay=False, can_pay_balance=False, show_top_up=False, activation_url=_activation_link_for_order(order)),
    )
    if order.delivered_payload:
        await message.answer(t("orders_delivery_message", user.language).format(payload=order.delivered_payload))
    elif order_before is not None and order_before.status == OrderStatus.PENDING and order.status == OrderStatus.PROCESSING:
        await _notify_admins_manual_order(callback=callback, order=order, offer=offer if order is not None else None, user=user)
    await callback.answer(t("orders_payment_success_toast", user.language))


@router.callback_query(F.data == CALLBACK_ORDERS_TOP_UP)
async def on_order_top_up(callback: CallbackQuery, state: FSMContext) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    await state.set_state(TopUpStates.choosing_method)
    await message.answer(
        t("top_up_main", user.language).format(balance=format_money(user.balance)),
        reply_markup=top_up_main_keyboard(user.language, show_bybit=_is_bybit_available_for_top_up()),
    )
    await callback.answer()
