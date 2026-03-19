from math import ceil

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.products import show_root_categories
from app.bot.i18n import t
from app.bot.keyboards.account import (
    CALLBACK_ORDERS_BACK,
    CALLBACK_ORDERS_MENU,
    CALLBACK_ORDERS_OPEN,
    CALLBACK_ORDERS_PAGE,
    CALLBACK_ORDERS_PAY,
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
from app.models.enums import Language, OrderStatus
from app.models.order import Order
from app.models.user import User
from app.bot.handlers.top_up import TopUpStates
from app.services.orders import count_user_orders, get_user_order, get_user_order_stats, list_user_orders, pay_pending_order_from_balance
from app.services.users import get_user_by_telegram_id, init_or_update_user

router = Router(name="menu")
ORDERS_PER_PAGE = 5


def _format_dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _order_status_label(status: OrderStatus, language: Language) -> str:
    return t(f"orders_status_{status.value}", language)


def _sanitize_payload(payload: str, limit: int = 300) -> str:
    safe_payload = payload.strip()
    if len(safe_payload) <= limit:
        return safe_payload
    return f"{safe_payload[:limit]}..."


def _render_orders_text(*, language: Language, orders: list[Order], page: int, pages: int, currency: str) -> str:
    lines = [t("orders_title", language).format(page=page, pages=pages), ""]

    for order in orders:
        lines.append(
            t("orders_card", language).format(
                id=order.id,
                created_at=_format_dt(order.created_at),
                status=_order_status_label(order.status, language),
                price=order.price,
                currency=currency,
            )
        )
        if order.status == OrderStatus.DELIVERED and order.delivered_payload:
            lines.append(t("orders_payload", language).format(payload=_sanitize_payload(order.delivered_payload)))
        lines.append("")

    return "\n".join(lines).strip()


def _render_order_details_text(*, language: Language, order: Order, currency: str) -> str:
    lines = [
        t("orders_details_title", language).format(id=order.id),
        t("orders_details_created", language).format(created_at=_format_dt(order.created_at)),
        t("orders_details_status", language).format(status=_order_status_label(order.status, language)),
        t("orders_details_price", language).format(price=order.price, currency=currency),
    ]
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
            balance=user.balance,
            currency=user.currency.value,
            total_orders=stats.total_orders,
            delivered_orders=stats.delivered_orders,
            total_spent=stats.total_spent,
        ),
        reply_markup=profile_keyboard(user.language),
    )


async def _show_orders(message: Message, user: User, page: int = 1) -> None:
    with SessionLocal() as db:
        total = count_user_orders(db, user_id=user.id)
        if total == 0:
            await message.answer(t("orders_empty", user.language), reply_markup=main_menu_keyboard(user.language))
            return

        pages = ceil(total / ORDERS_PER_PAGE)
        page = max(1, min(page, pages))
        orders = list_user_orders(db, user_id=user.id, limit=ORDERS_PER_PAGE, offset=(page - 1) * ORDERS_PER_PAGE)

    await message.answer(
        _render_orders_text(
            language=user.language,
            orders=orders,
            page=page,
            pages=pages,
            currency=user.currency.value,
        ),
        reply_markup=orders_keyboard(language=user.language, page=page, pages=pages, orders=orders),
    )


@router.message(F.text)
async def menu_handler(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None or not message.text:
        return

    key = menu_key_by_text(message.text)
    if key not in MENU_KEYS:
        return

    user = _resolve_or_create_user(tg_user)

    if key == "menu_profile":
        await _show_profile(message, user)
        return

    if key == "menu_orders":
        await _show_orders(message, user, page=1)
        return

    if key == "menu_products":
        await show_root_categories(message)
        return

    placeholders = {
        "menu_rules": "rules_placeholder",
        "menu_support": "support_placeholder",
    }
    if key == "menu_top_up":
        return
    await message.answer(t(placeholders[key], user.language), reply_markup=main_menu_keyboard(user.language))


@router.callback_query(F.data.in_({CALLBACK_PROFILE_BACK, CALLBACK_PROFILE_MENU, CALLBACK_ORDERS_BACK, CALLBACK_ORDERS_MENU}))
async def on_menu_return(callback: CallbackQuery) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return

    user = _resolve_or_create_user(callback.from_user)
    await message.answer(t("start", user.language), reply_markup=main_menu_keyboard(user.language))
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
            await message.answer(t("orders_empty", user.language), reply_markup=main_menu_keyboard(user.language))
            await callback.answer()
            return

        pages = ceil(total / ORDERS_PER_PAGE)
        page = max(1, min(page, pages))
        orders = list_user_orders(db, user_id=user.id, limit=ORDERS_PER_PAGE, offset=(page - 1) * ORDERS_PER_PAGE)

    await message.edit_text(
        _render_orders_text(
            language=user.language,
            orders=orders,
            page=page,
            pages=pages,
            currency=user.currency.value,
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

    await message.edit_text(
        _render_order_details_text(language=user.language, order=order, currency=user.currency.value),
        reply_markup=order_details_keyboard(
            language=user.language,
            order_id=order.id,
            can_pay=order.status == OrderStatus.PENDING,
            show_top_up=order.status == OrderStatus.PENDING,
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
        result = pay_pending_order_from_balance(db, user_id=user.id, order_id=order_id)
        order = get_user_order(db, user_id=user.id, order_id=order_id)
        current_user = get_user_by_telegram_id(db, user.telegram_id)

    if order is None:
        await callback.answer(t("orders_not_found", user.language), show_alert=True)
        return

    if not result.ok:
        if result.reason == "insufficient_balance":
            await message.edit_text(
                t("orders_payment_insufficient_balance", user.language).format(
                    balance=current_user.balance if current_user is not None else user.balance,
                    currency=user.currency.value,
                ),
                reply_markup=order_details_keyboard(
                    language=user.language,
                    order_id=order.id,
                    can_pay=True,
                    show_top_up=True,
                ),
            )
            await callback.answer()
            return

        await message.edit_text(
            t("orders_payment_not_available", user.language),
            reply_markup=order_details_keyboard(
                language=user.language,
                order_id=order.id,
                can_pay=False,
                show_top_up=False,
            ),
        )
        await callback.answer()
        return

    await message.edit_text(
        t("orders_payment_success", user.language) + "\n\n" + _render_order_details_text(language=user.language, order=order, currency=user.currency.value),
        reply_markup=order_details_keyboard(
            language=user.language,
            order_id=order.id,
            can_pay=False,
            show_top_up=False,
        ),
    )
    if order.delivered_payload:
        await message.answer(t("orders_delivery_message", user.language).format(payload=order.delivered_payload))
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
        t("top_up_main", user.language).format(balance=user.balance, currency=user.currency.value),
        reply_markup=top_up_main_keyboard(user.language),
    )
    await callback.answer()
