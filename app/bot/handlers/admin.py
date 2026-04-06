from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from sqlalchemy.orm import joinedload
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.admin import admin_menu_keyboard
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.money import format_money
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import FulfillmentType, Language, OrderStatus, TopUpMethod, TopUpStatus
from app.models.offer import Offer
from app.models.order import Order
from app.models.top_up_request import TopUpRequest
from app.services import admin as admin_service
from app.services.fulfillment import refresh_activation_task_status
from app.services.top_up_verification import verify_bybit_uid_top_up, verify_crypto_txid_top_up
from app.services.top_up_payments import check_crypto_pay_top_up
from app.services.users import get_user_by_telegram_id

router = Router(name="admin")


class AdminStates(StatesGroup):
    wait_categories = State()
    wait_offers = State()
    wait_price_update = State()
    wait_payload_add = State()
    wait_manual_order_status = State()


def _is_admin(telegram_id: int) -> bool:
    return admin_service.is_admin_telegram_id(telegram_id, get_settings().admin_telegram_ids)


def _safe_parse_int(raw: str, *, field_name: str) -> tuple[int | None, str | None]:
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, f"{field_name} должен быть числом"


def _parse_count_token(raw: str | None) -> tuple[int | str | None, str | None]:
    if raw is None or raw == "":
        return None, None
    if raw.lower() == "all":
        return "all", None
    parsed, error = _safe_parse_int(raw, field_name="count")
    if parsed is None:
        return None, error
    if parsed < 0:
        return None, "count должен быть >= 0 или all"
    return parsed, None


def _exit_language_for_user(telegram_id: int) -> Language:
    with SessionLocal() as db:
        user = get_user_by_telegram_id(db, telegram_id)
    if user is not None:
        return user.language
    return getattr(get_settings(), "default_language", Language.RU)


@router.message(Command("admin"))
async def admin_command(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id):
        return
    await message.answer("Админка WEBSTER-SHOP", reply_markup=admin_menu_keyboard())


@router.callback_query(StateFilter("*"), F.data == "adm:exit")
async def admin_exit(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    if callback.message is not None:
        language = _exit_language_for_user(callback.from_user.id)
        await callback.message.answer("Вы вышли из админки", reply_markup=main_menu_keyboard(language, is_admin=True))
    await callback.answer()


@router.callback_query(StateFilter("*"), F.data == "adm:products")
async def admin_products(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        categories = admin_service.list_categories_for_admin(db)
    lines = ["Категории:"] + [f"#{c.id} {c.name_ru}/{c.name_en} active={c.is_active}" for c in categories]
    lines += [
        "",
        "Добавить категорию: CAT|name_ru|name_en|description_ru|description_en",
        "Активность: TOGGLE_CAT|category_id|on/off",
        "Экспорт: EXPORT_CAT|category_id",
        "Удаление: DELETE_CAT|category_id",
    ]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_categories)
    await callback.answer()


@router.message(AdminStates.wait_categories, F.text.regexp(r"^(CAT\||TOGGLE_CAT\||EXPORT_CAT\||DELETE_CAT\|).+"))
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
            lines = [line.strip() for line in message.text.splitlines() if line.strip()]
            done = 0
            errors: list[str] = []
            for idx, line in enumerate(lines, start=1):
                if not line.startswith("TOGGLE_CAT|"):
                    errors.append(f"Строка {idx}: не начинается с TOGGLE_CAT|")
                    continue
                _, cid, mode = line.split("|", maxsplit=2)
                category_id, error = _safe_parse_int(cid, field_name="category_id")
                if category_id is None:
                    errors.append(f"Строка {idx}: {error}")
                    continue
                category = admin_service.update_category_activity(db, category_id=category_id, is_active=mode == "on")
                if category is None:
                    errors.append(f"Строка {idx}: категория не найдена")
                    continue
                done += 1
            answer = [f"TOGGLE_CAT выполнено: {done}"]
            if errors:
                answer.append("Ошибки:")
                answer.extend(errors)
            await message.answer("\n".join(answer))
            return
        if message.text.startswith("EXPORT_CAT|"):
            lines = [line.strip() for line in message.text.splitlines() if line.strip()]
            reports: list[str] = []
            for idx, line in enumerate(lines, start=1):
                if not line.startswith("EXPORT_CAT|"):
                    reports.append(f"Строка {idx}: не EXPORT_CAT команда")
                    continue
                _, cid = line.split("|", maxsplit=1)
                category_id, error = _safe_parse_int(cid, field_name="category_id")
                if category_id is None:
                    reports.append(f"Строка {idx}: {error}")
                    continue
                category, export_path = admin_service.export_category(db, category_id=category_id, reason="manual_export")
                reports.append(f"Строка {idx}: экспорт #{category_id} -> {export_path}" if category else f"Строка {idx}: категория не найдена")
            await message.answer("\n".join(reports))
            return
        if message.text.startswith("DELETE_CAT|"):
            lines = [line.strip() for line in message.text.splitlines() if line.strip()]
            reports: list[str] = []
            for idx, line in enumerate(lines, start=1):
                if not line.startswith("DELETE_CAT|"):
                    reports.append(f"Строка {idx}: не DELETE_CAT команда")
                    continue
                _, cid = line.split("|", maxsplit=1)
                category_id, error = _safe_parse_int(cid, field_name="category_id")
                if category_id is None:
                    reports.append(f"Строка {idx}: {error}")
                    continue
                ok, details = admin_service.delete_category(db, category_id=category_id)
                reports.append(f"Строка {idx}: {details}" if ok else f"Строка {idx}: ошибка {details}")
            await message.answer("\n".join(reports))
            return


@router.callback_query(StateFilter("*"), F.data == "adm:prices")
async def admin_prices(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("forbidden", show_alert=True)
        return
    await state.clear()
    with SessionLocal() as db:
        offers = admin_service.list_offers_for_admin(db)
    lines = ["Товары/офферы:"] + [
        f"#{o.id} cat={o.category_id} {o.name_ru} {o.fulfillment_type.value} price={format_money(o.base_price or 0)} active={o.is_active}"
        for o in offers
    ]
    lines += [
        "",
        "Добавить товар: OFFER|category_id|name_ru|name_en|fulfillment_type|price|description_ru|description_en",
        "Цена: PRICE|offer_id|amount",
        "Активность: TOGGLE_OFFER|offer_id|on/off",
        "Экспорт: EXPORT_OFFER|offer_id|count(optional, all/число)",
        "Удаление: DELETE_OFFER|offer_id|count(optional, all/число)",
        "Баланс: BALANCE|telegram_id|set/add/sub|amount",
    ]
    await callback.message.answer("\n".join(lines))
    await state.set_state(AdminStates.wait_offers)
    await callback.answer()


@router.message(AdminStates.wait_offers, F.text.regexp(r"^(OFFER\||PRICE\||TOGGLE_OFFER\||EXPORT_OFFER\||DELETE_OFFER\||BALANCE\|).+"))
async def admin_offer_input(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    with SessionLocal() as db:
        if message.text.startswith("OFFER|"):
            lines = [line.strip() for line in message.text.splitlines() if line.strip()]
            created_ids: list[int] = []
            errors: list[str] = []
            for idx, line in enumerate(lines, start=1):
                if not line.startswith("OFFER|"):
                    errors.append(f"Строка {idx}: не начинается с OFFER|")
                    continue
                parts = line.split("|")
                if len(parts) < 6:
                    errors.append(f"Строка {idx}: недостаточно полей")
                    continue
                _, category_id, name_ru, name_en, ft_raw, price_raw, *desc = parts
                try:
                    ft = FulfillmentType(ft_raw)
                    price = Decimal(price_raw)
                except (ValueError, InvalidOperation):
                    errors.append(f"Строка {idx}: неверные fulfillment_type/price")
                    continue
                parsed_category_id, category_error = _safe_parse_int(category_id, field_name="category_id")
                if parsed_category_id is None:
                    errors.append(f"Строка {idx}: {category_error}")
                    continue
                offer = admin_service.create_offer(
                    db,
                    category_id=parsed_category_id,
                    name_ru=name_ru,
                    name_en=name_en,
                    description_ru=desc[0] if desc else None,
                    description_en=desc[1] if len(desc) > 1 else (desc[0] if desc else None),
                    fulfillment_type=ft,
                    base_price=price,
                )
                if offer is None:
                    errors.append(f"Строка {idx}: категория не найдена")
                else:
                    created_ids.append(offer.id)
            summary = [f"Создано офферов: {len(created_ids)}"]
            if created_ids:
                summary.append("ID: " + ", ".join(str(i) for i in created_ids))
            if errors:
                summary.append("Ошибки:")
                summary.extend(errors)
            await message.answer("\n".join(summary))
            return

        if message.text.startswith("PRICE|"):
            _, offer_id, amount_raw = message.text.split("|", maxsplit=2)
            parsed_offer_id, error = _safe_parse_int(offer_id, field_name="offer_id")
            if parsed_offer_id is None:
                await message.answer(error)
                return
            try:
                amount = Decimal(amount_raw)
            except InvalidOperation:
                await message.answer("Некорректная сумма")
                return
            offer = admin_service.update_offer_price(db, offer_id=parsed_offer_id, price=amount)
            await message.answer("Цена обновлена" if offer else "Товар не найден")
            return
        if message.text.startswith("TOGGLE_OFFER|"):
            lines = [line.strip() for line in message.text.splitlines() if line.strip()]
            done = 0
            errors: list[str] = []
            for idx, line in enumerate(lines, start=1):
                if not line.startswith("TOGGLE_OFFER|"):
                    errors.append(f"Строка {idx}: не TOGGLE_OFFER команда")
                    continue
                _, oid, mode = line.split("|", maxsplit=2)
                offer_id, error = _safe_parse_int(oid, field_name="offer_id")
                if offer_id is None:
                    errors.append(f"Строка {idx}: {error}")
                    continue
                offer = admin_service.update_offer_activity(db, offer_id=offer_id, is_active=mode == "on")
                if offer is None:
                    errors.append(f"Строка {idx}: товар не найден")
                    continue
                done += 1
            answer = [f"TOGGLE_OFFER выполнено: {done}"]
            if errors:
                answer.append("Ошибки:")
                answer.extend(errors)
            await message.answer("\n".join(answer))
            return
        if message.text.startswith("EXPORT_OFFER|"):
            lines = [line.strip() for line in message.text.splitlines() if line.strip()]
            reports: list[str] = []
            for idx, line in enumerate(lines, start=1):
                if not line.startswith("EXPORT_OFFER|"):
                    reports.append(f"Строка {idx}: не EXPORT_OFFER команда")
                    continue
                parts = line.split("|")
                if len(parts) < 2:
                    reports.append(f"Строка {idx}: недостаточно полей")
                    continue
                offer_id, error = _safe_parse_int(parts[1], field_name="offer_id")
                if offer_id is None:
                    reports.append(f"Строка {idx}: {error}")
                    continue
                count, count_error = _parse_count_token(parts[2] if len(parts) > 2 else None)
                if count_error:
                    reports.append(f"Строка {idx}: {count_error}")
                    continue
                offer, export_path, summary = admin_service.export_offer(db, offer_id=offer_id, reason="manual_export", count=count)
                if offer is None:
                    reports.append(f"Строка {idx}: товар не найден")
                    continue
                reports.append(
                    f"Строка {idx}: экспорт #{offer_id} -> {export_path}; найдено={summary.get('available_found', 0)} выгружено={summary.get('exported', 0)} не обработано={summary.get('skipped', 0)}"
                )
            await message.answer("\n".join(reports))
            return
        if message.text.startswith("DELETE_OFFER|"):
            lines = [line.strip() for line in message.text.splitlines() if line.strip()]
            reports: list[str] = []
            for idx, line in enumerate(lines, start=1):
                if not line.startswith("DELETE_OFFER|"):
                    reports.append(f"Строка {idx}: не DELETE_OFFER команда")
                    continue
                parts = line.split("|")
                if len(parts) < 2:
                    reports.append(f"Строка {idx}: недостаточно полей")
                    continue
                offer_id, error = _safe_parse_int(parts[1], field_name="offer_id")
                if offer_id is None:
                    reports.append(f"Строка {idx}: {error}")
                    continue
                count, count_error = _parse_count_token(parts[2] if len(parts) > 2 else None)
                if count_error:
                    reports.append(f"Строка {idx}: {count_error}")
                    continue
                ok, details = admin_service.delete_offer(db, offer_id=offer_id, count=count)
                reports.append(f"Строка {idx}: {details}" if ok else f"Строка {idx}: ошибка {details}")
            await message.answer("\n".join(reports))
            return
        if message.text.startswith("BALANCE|"):
            _, tg_id_raw, action, amount_raw = message.text.split("|", maxsplit=3)
            try:
                tg_id = int(tg_id_raw)
                amount = Decimal(amount_raw)
            except (ValueError, InvalidOperation):
                await message.answer("Некорректный telegram_id/amount")
                return
            if amount < 0:
                await message.answer("Сумма должна быть >= 0")
                return
            ok, info, old_balance, new_balance = admin_service.update_user_balance_by_telegram_id(
                db,
                telegram_id=tg_id,
                action=action,
                amount=amount,
            )
            if not ok:
                await message.answer(info)
                return
            await message.answer(
                f"Пользователь: {tg_id}\nСтарый баланс: {format_money(old_balance or 0)}\nНовый баланс: {format_money(new_balance or 0)}"
            )


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
    rows: list[tuple[int, str]] = []
    errors: list[str] = []
    for idx, line in enumerate([line.strip() for line in message.text.splitlines() if line.strip()], start=1):
        if not line.startswith("PAYLOAD|"):
            errors.append(f"Строка {idx}: не PAYLOAD команда")
            continue
        parts = line.split("|", maxsplit=2)
        if len(parts) < 3:
            errors.append(f"Строка {idx}: недостаточно полей")
            continue
        _, offer_id, payload = parts
        parsed_offer_id, error = _safe_parse_int(offer_id, field_name="offer_id")
        if parsed_offer_id is None:
            errors.append(f"Строка {idx}: {error}")
            continue
        rows.append((parsed_offer_id, payload))
    with SessionLocal() as db:
        added, service_errors = admin_service.add_direct_stock_payload_batch(db, rows=rows)
    all_errors = errors + service_errors
    summary = [f"Добавлено payload: {added}"]
    if all_errors:
        summary.append("Ошибки:")
        summary.extend(all_errors)
    await message.answer("\n".join(summary))


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
        order_id, error = _safe_parse_int(order_id_raw, field_name="order_id")
        if order_id is None:
            await message.answer(error)
            return
        new_status = OrderStatus.DELIVERED if status_raw == "delivered" else OrderStatus.CANCELED
        with SessionLocal() as db:
            order = admin_service.update_order_status_for_manual_supplier(db, order_id=order_id, new_status=new_status)
        await message.answer("Статус обновлен" if order else "Нельзя изменить этот заказ")
        return

    if message.text.startswith("ACT|"):
        _, order_id_raw = message.text.split("|", maxsplit=1)
        order_id, error = _safe_parse_int(order_id_raw, field_name="order_id")
        if order_id is None:
            await message.answer(error)
            return
        with SessionLocal() as db:
            order = db.get(Order, order_id)
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
    order_id, error = _safe_parse_int(order_id_raw, field_name="order_id")
    if order_id is None:
        await message.answer(error)
        return
    new_status = OrderStatus.DELIVERED if status_raw == "delivered" else OrderStatus.CANCELED

    with SessionLocal() as db:
        order = admin_service.update_order_status_for_manual_supplier(
            db,
            order_id=order_id,
            new_status=new_status,
        )

    await message.answer("Статус обновлен" if order else "Нельзя изменить этот заказ")

@router.message(StateFilter("*"), F.text.startswith("ACT|"))
async def admin_activation_refresh_global(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return

    _, order_id_raw = message.text.split("|", maxsplit=1)
    order_id, error = _safe_parse_int(order_id_raw, field_name="order_id")
    if order_id is None:
        await message.answer(error)
        return

    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if order is None:
            await message.answer("Заказ не найден")
            return
        result = refresh_activation_task_status(db, order=order)

    await message.answer(f"Проверка activation: {result.reason}")



@router.message(StateFilter("*"), F.text == "TOPUPS")
async def admin_topups_list(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id):
        return
    with SessionLocal() as db:
        requests = admin_service.list_recent_top_up_requests(db)
    lines = ["Top up requests:"]
    for req in requests:
        lines.append(
            f"#{req.id} user={req.user_id} method={req.method.value} status={req.status.value} source={req.verification_source} net={req.net_amount} fee={req.fee_amount} gross={req.gross_amount}"
        )
    lines.append("")
    lines.append("Verify: TOPUP_VERIFY|request_id|verified/rejected/expired|note(optional)")
    await message.answer("\n".join(lines))


@router.message(StateFilter("*"), F.text.startswith("TOPUP_VERIFY|"))
async def admin_topup_verify(message: Message) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id) or not message.text:
        return
    _, request_id_raw, status_raw, *rest = message.text.split("|", maxsplit=3)
    request_id, error = _safe_parse_int(request_id_raw, field_name="request_id")
    if request_id is None:
        await message.answer(error)
        return
    note = rest[0] if rest else None
    try:
        target_status = TopUpStatus(status_raw)
    except ValueError:
        await message.answer("Invalid status. Use: verified/rejected/expired")
        return

    with SessionLocal() as db:
        req = db.get(TopUpRequest, request_id)
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
