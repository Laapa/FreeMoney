from math import ceil

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.products import show_root_categories
from app.bot.i18n import t
from app.bot.keyboards.account import (
    CALLBACK_ORDERS_BACK,
    CALLBACK_ORDERS_MENU,
    CALLBACK_ORDERS_PAGE,
    CALLBACK_PROFILE_BACK,
    CALLBACK_PROFILE_MENU,
    orders_keyboard,
    profile_keyboard,
)
from app.bot.keyboards.main_menu import MENU_KEYS, main_menu_keyboard, menu_key_by_text
from app.db.session import SessionLocal
from app.models.enums import Language, OrderStatus
from app.models.order import Order
from app.models.user import User
from app.services.orders import count_user_orders, get_user_order_stats, list_user_orders
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
        reply_markup=orders_keyboard(language=user.language, page=page, pages=pages),
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
        "menu_top_up": "top_up_placeholder",
        "menu_rules": "rules_placeholder",
        "menu_support": "support_placeholder",
    }
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
        reply_markup=orders_keyboard(language=user.language, page=page, pages=pages),
    )
    await callback.answer()
