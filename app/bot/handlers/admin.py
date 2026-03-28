from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.filters import Command
from sqlalchemy.orm import joinedload
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.admin import admin_menu_keyboard
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import FulfillmentType, OrderStatus, TopUpMethod, TopUpStatus
from app.models.offer import Offer
from app.models.order import Order
from app.models.top_up_request import TopUpRequest
from app.services import admin as admin_service
from app.services.fulfillment import refresh_activation_task_status
from app.services.top_up_verification import verify_bybit_uid_top_up, verify_crypto_txid_top_up
from app.services.top_up_payments import check_crypto_pay_top_up

router = Router(name="admin")


class AdminStates(StatesGroup):
    wait_categories = State()
    wait_offers = State()
    wait_price_update = State()
    wait_payload_add = State()
    wait_manual_order_status = State()


def _is_admin(telegram_id: int) -> bool:
    return admin_service.is_admin_telegram_id(telegram_id, get_settings().admin_telegram_ids)


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id):
        return
    await message.answer("Админка WEBSTER-SHOP", reply_markup=admin_menu_keyboard())


@router.callback_query(StateFilter("*"), F.data == "adm:products")
async def admin_products(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        categories = admin_service.list_categories_for_admin(db)
    lines = ["Категории:"] + [f"#{c.id} {c.name_ru}/{c.name_en} active={c.is_active}" for c in categories]
    lines += ["", "Добавить категорию: CAT|name_ru|name_en|description_ru|description_en", "Активность: TOGGLE_CAT|category_id|on/off"]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_categories)
    await callback.answer()


@router.message(AdminStates.wait_categories)
async def admin_categories_input(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    with SessionLocal() as db:
        if message.text.startswith("CAT|"):
            _, name_ru, name_en, *desc = message.text.split("|")
            category = admin_service.create_category(
                db,
                name_ru=name_ru,
                name_en=name_en,
                description_ru=desc[0] if desc else None,
                description_en=desc[1] if len(desc) > 1 else (desc[0] if desc else None),
            )
            await message.answer(f"Категория создана #{category.id}")
            return
        if message.text.startswith("TOGGLE_CAT|"):
            _, cid, mode = message.text.split("|", maxsplit=2)
            category = admin_service.update_category_activity(db, category_id=int(cid), is_active=mode == "on")
            await message.answer("Обновлено" if category else "Категория не найдена")
            return
    await message.answer("Формат: CAT|... или TOGGLE_CAT|...")


@router.callback_query(StateFilter("*"), F.data == "adm:prices")
async def admin_prices(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        offers = admin_service.list_offers_for_admin(db)
    lines = ["Товары/офферы:"] + [f"#{o.id} cat={o.category_id} {o.name_ru} {o.fulfillment_type.value} price={o.base_price}" for o in offers]
    lines += ["", "Добавить товар: OFFER|category_id|name_ru|name_en|fulfillment_type|price|description_ru|description_en", "Цена: PRICE|offer_id|amount"]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_offers)
    await callback.answer()


@router.message(AdminStates.wait_offers)
async def admin_offer_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    with SessionLocal() as db:
        if message.text.startswith("OFFER|"):
            _, category_id, name_ru, name_en, ft_raw, price_raw, *desc = message.text.split("|")
            try:
                ft = FulfillmentType(ft_raw)
                price = Decimal(price_raw)
            except (ValueError, InvalidOperation):
                await message.answer("Неверные fulfillment_type/price")
                return
            offer = admin_service.create_offer(
                db,
                category_id=int(category_id),
                name_ru=name_ru,
                name_en=name_en,
                description_ru=desc[0] if desc else None,
                description_en=desc[1] if len(desc) > 1 else (desc[0] if desc else None),
                fulfillment_type=ft,
                base_price=price,
            )
            await message.answer(f"Товар добавлен #{offer.id}" if offer else "Категория не найдена")
            return

        if message.text.startswith("PRICE|"):
            _, offer_id, amount_raw = message.text.split("|", maxsplit=2)
            try:
                amount = Decimal(amount_raw)
            except InvalidOperation:
                await message.answer("Некорректная сумма")
                return
            offer = admin_service.update_offer_price(db, offer_id=int(offer_id), price=amount)
            await message.answer("Цена обновлена" if offer else "Товар не найден")
            return

    await message.answer("Формат: OFFER|... или PRICE|...")


@router.callback_query(StateFilter("*"), F.data == "adm:stock")
async def admin_stock(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        offers = [o for o in admin_service.list_offers_for_admin(db) if o.fulfillment_type == FulfillmentType.DIRECT_STOCK]
        lines = ["Пул прямой выдачи:"] + [f"offer #{o.id} {o.name_ru}: {admin_service.available_payload_count(db, offer_id=o.id)}" for o in offers]
    lines += ["", "Добавить payload: PAYLOAD|offer_id|text"]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_payload_add)
    await callback.answer()


@router.message(AdminStates.wait_payload_add)
async def admin_payload_add_input(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    if not message.text.startswith("PAYLOAD|"):
        await message.answer("Формат: PAYLOAD|offer_id|text")
        return
    _, offer_id, payload = message.text.split("|", maxsplit=2)
    with SessionLocal() as db:
        product = admin_service.add_direct_stock_payload(db, offer_id=int(offer_id), payload=payload)
    await message.answer("Payload добавлен" if product else "Товар не найден или не direct_stock")


@router.callback_query(StateFilter("*"), F.data == "adm:orders")
async def admin_orders(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return

    await state.clear()

    with SessionLocal() as db:
        orders = admin_service.list_recent_orders(db)
        order_rows = []

        offer_ids = {o.offer_id for o in orders}
        offers = (
            db.query(Offer)
            .options(joinedload(Offer.category))
            .filter(Offer.id.in_(offer_ids))
            .all()
            if offer_ids
            else []
        )
        offer_map = {o.id: o for o in offers}

        for order in orders:
            offer = offer_map.get(order.offer_id)
            offer_name = offer.name_ru if offer else f"offer#{order.offer_id}"
            category_name = offer.category.name_ru if offer and offer.category else "-"
            order_rows.append(
    f"order #{order.id} | {category_name} | {offer_name} | {order.price} | {order.status.value}"
)

    lines = ["Последние заказы:", *order_rows]
    lines += ["", "Manual status: MANUAL|order_id|delivered/canceled", "Activation refresh: ACT|order_id"]

    await callback.message.answer("\n".join(lines))
    await callback.answer()

@router.message(AdminStates.wait_manual_order_status)
async def admin_order_update_input(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return

    if message.text.startswith("MANUAL|"):
        _, order_id_raw, status_raw = message.text.split("|", maxsplit=2)
        new_status = OrderStatus.DELIVERED if status_raw == "delivered" else OrderStatus.CANCELED
        with SessionLocal() as db:
            order = admin_service.update_order_status_for_manual_supplier(db, order_id=int(order_id_raw), new_status=new_status)
        await message.answer("Статус обновлен" if order else "Нельзя изменить этот заказ")
        return

    if message.text.startswith("ACT|"):
        _, order_id_raw = message.text.split("|", maxsplit=1)
        with SessionLocal() as db:
            order = db.get(Order, int(order_id_raw))
            if order is None:
                await message.answer("Заказ не найден")
                return
            result = refresh_activation_task_status(db, order=order)
        await message.answer(f"Проверка activation: {result.reason}")
        return

@router.message(StateFilter("*"), F.text.startswith("MANUAL|"))
async def admin_order_update_global(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return

    _, order_id_raw, status_raw = message.text.split("|", maxsplit=2)
    new_status = OrderStatus.DELIVERED if status_raw == "delivered" else OrderStatus.CANCELED

    with SessionLocal() as db:
        order = admin_service.update_order_status_for_manual_supplier(
            db,
            order_id=int(order_id_raw),
            new_status=new_status,
        )

    await message.answer("Статус обновлен" if order else "Нельзя изменить этот заказ")

@router.message(StateFilter("*"), F.text.startswith("ACT|"))
async def admin_activation_refresh_global(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return

    _, order_id_raw = message.text.split("|", maxsplit=1)

    with SessionLocal() as db:
        order = db.get(Order, int(order_id_raw))
        if order is None:
            await message.answer("Заказ не найден")
            return
        result = refresh_activation_task_status(db, order=order)

    await message.answer(f"Проверка activation: {result.reason}")

    await message.answer("Формат: MANUAL|order_id|delivered/canceled или ACT|order_id")


@router.message(StateFilter("*"), F.text == "TOPUPS")
async def admin_topups_list(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id):
        return
    with SessionLocal() as db:
        requests = admin_service.list_recent_top_up_requests(db)
    lines = ["Top up requests:"]
    for req in requests:
        lines.append(
            f"#{req.id} user={req.user_id} method={req.method.value} status={req.status.value} net={req.net_amount} fee={req.fee_amount} gross={req.gross_amount}"
        )
    lines.append("")
    lines.append("Verify: TOPUP_VERIFY|request_id|verified/rejected/expired|note(optional)")
    await message.answer("\n".join(lines))


@router.message(StateFilter("*"), F.text.startswith("TOPUP_VERIFY|"))
async def admin_topup_verify(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    _, request_id_raw, status_raw, *rest = message.text.split("|", maxsplit=3)
    note = rest[0] if rest else None
    target_status = TopUpStatus(status_raw)

    with SessionLocal() as db:
        req = db.get(TopUpRequest, int(request_id_raw))
        if req is None:
            await message.answer("Top-up request not found")
            return
        if req.method == TopUpMethod.BYBIT_UID:
            result = verify_bybit_uid_top_up(db, request_id=req.id, target_status=target_status, verification_note=note)
            await message.answer("OK" if result.ok else f"ERROR: {result.error}")
            return
        if req.method == TopUpMethod.CRYPTO_TXID:
            result = verify_crypto_txid_top_up(db, request_id=req.id, target_status=target_status, verification_note=note)
            await message.answer("OK" if result.ok else f"ERROR: {result.error}")
            return
        if req.method == TopUpMethod.CRYPTO_PAY:
            result = check_crypto_pay_top_up(db, request_id=req.id)
            await message.answer(f"Crypto Pay check: {result.reason}")
            return
