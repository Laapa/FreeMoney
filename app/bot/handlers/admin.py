from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.admin import admin_menu_keyboard
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import FulfillmentType, OrderStatus
from app.models.order import Order
from app.services import admin as admin_service
from app.services.fulfillment import refresh_activation_task_status

router = Router(name="admin")


class AdminStates(StatesGroup):
    wait_create_category = State()
    wait_price_update = State()
    wait_payload_add = State()
    wait_toggle_item = State()
    wait_manual_order_status = State()


def _is_admin(telegram_id: int) -> bool:
    return admin_service.is_admin_telegram_id(telegram_id, get_settings().admin_telegram_ids)


def _format_category_line(category) -> str:
    return (
        f"#{category.id} | {category.name_ru} / {category.name_en} | "
        f"{category.fulfillment_type.value} | active={category.is_active} | price={category.base_price}"
    )


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id):
        return
    await message.answer("Админка WEBSTER-SHOP", reply_markup=admin_menu_keyboard())


@router.message(F.text.in_({"🛠 Админка", "🛠 Admin"}))
async def admin_from_menu(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id):
        return
    await message.answer("Админка WEBSTER-SHOP", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "adm:products")
async def admin_products(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        categories = admin_service.list_categories_for_admin(db)
    lines = ["Товары:"] + [_format_category_line(item) for item in categories]
    lines += ["", "Добавить: отправьте -> ADD|name_ru|name_en|fulfillment_type|price|description_ru|description_en"]
    lines += ["Отключить/включить: TOGGLE|category_id|on/off"]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_create_category)
    await callback.answer()


@router.message(AdminStates.wait_create_category)
async def admin_products_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    text = message.text.strip()
    with SessionLocal() as db:
        if text.startswith("ADD|"):
            parts = text.split("|")
            if len(parts) < 6:
                await message.answer("Формат: ADD|name_ru|name_en|fulfillment_type|price|description_ru|description_en")
                return
            _, name_ru, name_en, fulfillment_raw, price_raw, *descriptions = parts
            try:
                fulfillment = FulfillmentType(fulfillment_raw)
                price = Decimal(price_raw)
            except (ValueError, InvalidOperation):
                await message.answer("Неверный fulfillment_type или price")
                return
            description_ru = descriptions[0] if descriptions else None
            description_en = descriptions[1] if len(descriptions) > 1 else description_ru
            category = admin_service.create_category(
                db,
                name_ru=name_ru,
                name_en=name_en,
                description_ru=description_ru,
                description_en=description_en,
                fulfillment_type=fulfillment,
                base_price=price,
            )
            await message.answer(f"Создана категория #{category.id}")
            return

        if text.startswith("TOGGLE|"):
            _, category_id_raw, mode = text.split("|", maxsplit=2)
            category = admin_service.update_category_activity(
                db,
                category_id=int(category_id_raw),
                is_active=mode.lower() == "on",
            )
            await message.answer("Обновлено" if category else "Категория не найдена")
            return

    await message.answer("Неизвестная команда")


@router.callback_query(F.data == "adm:prices")
async def admin_prices(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        categories = admin_service.list_categories_for_admin(db)
    lines = ["Цены:"] + [f"#{item.id} {item.name_ru}: {item.base_price}" for item in categories]
    lines += ["", "Изменить цену: PRICE|category_id|amount"]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_price_update)
    await callback.answer()


@router.message(AdminStates.wait_price_update)
async def admin_price_update_input(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    if not message.text.startswith("PRICE|"):
        await message.answer("Формат: PRICE|category_id|amount")
        return
    _, category_id_raw, amount_raw = message.text.split("|", maxsplit=2)
    try:
        amount = Decimal(amount_raw)
    except InvalidOperation:
        await message.answer("Некорректная сумма")
        return
    with SessionLocal() as db:
        category = admin_service.update_category_price(db, category_id=int(category_id_raw), price=amount)
    await message.answer("Цена обновлена" if category else "Категория не найдена")


@router.callback_query(F.data == "adm:stock")
async def admin_stock(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        categories = admin_service.list_categories_for_admin(db)
        direct = [item for item in categories if item.fulfillment_type == FulfillmentType.DIRECT_STOCK]
        lines = ["Пул прямой выдачи:"]
        for item in direct:
            count = admin_service.available_payload_count(db, category_id=item.id)
            lines.append(f"#{item.id} {item.name_ru}: {count}")
    lines += ["", "Добавить payload: PAYLOAD|category_id|text"]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_payload_add)
    await callback.answer()


@router.message(AdminStates.wait_payload_add)
async def admin_payload_add_input(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    if not message.text.startswith("PAYLOAD|"):
        await message.answer("Формат: PAYLOAD|category_id|text")
        return
    _, category_id_raw, payload = message.text.split("|", maxsplit=2)
    with SessionLocal() as db:
        product = admin_service.add_direct_stock_payload(db, category_id=int(category_id_raw), payload=payload)
    await message.answer("Payload добавлен" if product else "Категория не найдена или не direct_stock")


@router.callback_query(F.data == "adm:orders")
async def admin_orders(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        orders = admin_service.list_recent_orders(db)
    lines = ["Последние заказы:"]
    for order in orders:
        lines.append(
            f"#{order.id} user={order.user_id} cat={order.category_id} amount={order.price} "
            f"status={order.status.value} ft={order.fulfillment_type.value} ext_task={order.external_task_id or '-'}"
        )
    lines += ["", "Manual status: MANUAL|order_id|delivered/canceled", "Activation refresh: ACT|order_id"]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_manual_order_status)
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

    await message.answer("Формат: MANUAL|order_id|delivered/canceled или ACT|order_id")
