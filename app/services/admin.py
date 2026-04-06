from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import FulfillmentStatus, FulfillmentType, OrderStatus, ProductStatus
from app.models.offer import Offer
from app.models.order import Order
from app.models.product_pool import ProductPool
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.admin_exports import (
    export_category_with_offers_snapshot,
    export_offer_leftovers_snapshot,
    export_offer_snapshot,
)


def is_admin_telegram_id(telegram_id: int, admin_ids: set[int]) -> bool:
    return telegram_id in admin_ids


def list_categories_for_admin(db: Session) -> list[Category]:
    return db.scalars(select(Category).order_by(Category.id)).all()


def create_category(db: Session, *, name_ru: str, name_en: str, description_ru: str | None, description_en: str | None) -> Category:
    category = Category(name_ru=name_ru, name_en=name_en, description_ru=description_ru, description_en=description_en, is_active=True)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category_activity(db: Session, *, category_id: int, is_active: bool) -> Category | None:
    category = db.get(Category, category_id)
    if category is None:
        return None
    category.is_active = is_active
    db.commit()
    db.refresh(category)
    return category


def create_offer(
    db: Session,
    *,
    category_id: int,
    name_ru: str,
    name_en: str,
    description_ru: str | None,
    description_en: str | None,
    fulfillment_type: FulfillmentType,
    base_price: Decimal | None,
) -> Offer | None:
    category = db.get(Category, category_id)
    if category is None:
        return None
    offer = Offer(
        category_id=category_id,
        name_ru=name_ru,
        name_en=name_en,
        description_ru=description_ru,
        description_en=description_en,
        fulfillment_type=fulfillment_type,
        base_price=base_price,
        is_active=True,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


def list_offers_for_admin(db: Session, *, category_id: int | None = None) -> list[Offer]:
    query = select(Offer)
    if category_id is not None:
        query = query.where(Offer.category_id == category_id)
    return db.scalars(query.order_by(Offer.id)).all()


def update_offer_price(db: Session, *, offer_id: int, price: Decimal) -> Offer | None:
    offer = db.get(Offer, offer_id)
    if offer is None:
        return None
    offer.base_price = price
    db.commit()
    db.refresh(offer)
    return offer


def update_offer_activity(db: Session, *, offer_id: int, is_active: bool) -> Offer | None:
    offer = db.get(Offer, offer_id)
    if offer is None:
        return None
    offer.is_active = is_active
    db.commit()
    db.refresh(offer)
    return offer


def _parse_count(count: int | str | None) -> int | None:
    if count is None:
        return None
    if isinstance(count, int):
        return max(count, 0)
    if count.lower() == "all":
        return None
    return max(int(count), 0)


def _available_direct_stock_products_query(*, offer_id: int):
    return (
        select(ProductPool)
        .where(
            ProductPool.offer_id == offer_id,
            ProductPool.status == ProductStatus.AVAILABLE,
            ProductPool.removed_from_pool.is_(False),
        )
        .order_by(ProductPool.id.asc())
    )


def _take_count(items: list[ProductPool], count: int | None) -> list[ProductPool]:
    if count is None:
        return items
    return items[:count]


def _direct_stock_available_count(db: Session, *, offer_id: int) -> int:
    return db.scalar(
        select(func.count(ProductPool.id)).where(
            ProductPool.offer_id == offer_id,
            ProductPool.status == ProductStatus.AVAILABLE,
            ProductPool.removed_from_pool.is_(False),
        )
    ) or 0


def _try_delete_entity(db: Session, entity: object) -> tuple[bool, str | None]:
    try:
        with db.begin_nested():
            db.delete(entity)
            db.flush()
        return True, None
    except IntegrityError as exc:
        return False, str(exc.orig) if exc.orig else str(exc)


def _remove_products_from_pool(db: Session, products: list[ProductPool]) -> tuple[int, int, int]:
    deleted = 0
    archived = 0
    failed = 0
    for product in products:
        ok, _ = _try_delete_entity(db, product)
        if ok:
            deleted += 1
            continue
        product.removed_from_pool = True
        product.status = ProductStatus.AVAILABLE
        archived += 1
    return deleted, archived, failed


def export_offer(
    db: Session,
    *,
    offer_id: int,
    reason: str,
    count: int | str | None = None,
) -> tuple[Offer | None, str | None, dict[str, int | str]]:
    offer = db.get(Offer, offer_id)
    if offer is None:
        return None, None, {}
    if offer.fulfillment_type == FulfillmentType.DIRECT_STOCK:
        parsed_count = _parse_count(count)
        all_available = db.scalars(_available_direct_stock_products_query(offer_id=offer.id)).all()
        selected = _take_count(all_available, parsed_count)
        result = export_offer_leftovers_snapshot(db, offer=offer, reason=reason, leftovers=selected)
        summary = {
            "available_found": len(all_available),
            "exported": len(selected),
            "skipped": max(len(all_available) - len(selected), 0),
        }
        return offer, str(result.file_path), summary
    result = export_offer_snapshot(db, offer=offer, reason=reason)
    return offer, str(result.file_path), {"available_found": 0, "exported": 0, "skipped": 0}


def delete_offer(db: Session, *, offer_id: int, count: int | str | None = None) -> tuple[bool, str]:
    offer = db.get(Offer, offer_id)
    if offer is None:
        return False, "Товар не найден"

    if offer.fulfillment_type == FulfillmentType.DIRECT_STOCK:
        parsed_count = _parse_count(count)
        all_available = db.scalars(_available_direct_stock_products_query(offer_id=offer.id)).all()
        selected = _take_count(all_available, parsed_count)
        export_result = export_offer_leftovers_snapshot(db, offer=offer, reason="delete_offer_leftovers", leftovers=selected)
        deleted, archived, failed = _remove_products_from_pool(db, selected)
        remaining_available = _direct_stock_available_count(db, offer_id=offer.id)

        hard_deleted = False
        hidden_fallback = False
        fallback_reason: str | None = None
        if remaining_available == 0:
            hard_deleted, fallback_reason = _try_delete_entity(db, offer)
            if not hard_deleted:
                offer.is_active = False
                hidden_fallback = True

        db.commit()
        if hard_deleted:
            return (
                True,
                f"Оффер физически удален. Доступно: {len(all_available)}, удалено остатков: {deleted}, "
                f"архивировано: {archived}, не удалось обработать: {failed}. Snapshot: {export_result.file_path}",
            )
        if hidden_fallback:
            return (
                True,
                "Оффер выведен из меню, история сохранена. "
                f"Доступно: {len(all_available)}, удалено остатков: {deleted}, архивировано: {archived}, не удалось обработать: {failed}. "
                f"Причина fallback: {fallback_reason}. Snapshot: {export_result.file_path}",
            )
        return (
            True,
            "Остатки direct_stock обработаны. "
            f"Доступно: {len(all_available)}, удалено остатков: {deleted}, архивировано: {archived}, не удалось обработать: {failed}, "
            f"осталось доступных: {remaining_available}. "
            f"Snapshot: {export_result.file_path}",
        )

    export_result = export_offer_snapshot(db, offer=offer, reason="delete_offer")
    hard_deleted, fallback_reason = _try_delete_entity(db, offer)
    if hard_deleted:
        db.commit()
        return True, f"Товар физически удален. Snapshot: {export_result.file_path}"
    offer.is_active = False
    db.commit()
    return (
        True,
        "Товар выведен из активного меню, исторические записи сохранены. "
        f"Причина fallback: {fallback_reason}. Snapshot: {export_result.file_path}"
    )


def export_category(db: Session, *, category_id: int, reason: str) -> tuple[Category | None, str | None]:
    category = db.get(Category, category_id)
    if category is None:
        return None, None
    result = export_category_with_offers_snapshot(db, category=category, reason=reason)
    return category, str(result.file_path)


def delete_category(db: Session, *, category_id: int) -> tuple[bool, str]:
    category = db.get(Category, category_id)
    if category is None:
        return False, "Категория не найдена"
    export_result = export_category_with_offers_snapshot(db, category=category, reason="delete_category")
    offers = list_offers_for_admin(db, category_id=category.id)
    processed = 0
    removed_leftovers = 0
    offer_deleted_ids: list[int] = []
    offer_hidden_ids: list[int] = []

    for offer in offers:
        processed += 1
        if offer.fulfillment_type == FulfillmentType.DIRECT_STOCK:
            leftovers = db.scalars(_available_direct_stock_products_query(offer_id=offer.id)).all()
            deleted, archived, _ = _remove_products_from_pool(db, leftovers)
            removed_leftovers += deleted + archived
        hard_deleted, _ = _try_delete_entity(db, offer)
        if hard_deleted:
            offer_deleted_ids.append(offer.id)
            continue
        offer.is_active = False
        offer_hidden_ids.append(offer.id)

    hard_deleted_category, fallback_reason = _try_delete_entity(db, category)
    if hard_deleted_category:
        db.commit()
        return (
            True,
            "Категория физически удалена. "
            f"Офферов обработано: {processed}, офферы удалены: {offer_deleted_ids or '-'}, "
            f"офферы скрыты: {offer_hidden_ids or '-'}, удалено direct_stock остатков: {removed_leftovers}. "
            f"Snapshot: {export_result.file_path}",
        )

    category.is_active = False
    db.commit()
    return (
        True,
        "Категория и офферы выведены из активного меню, история сохранена. "
        f"Офферов обработано: {processed}, офферы удалены: {offer_deleted_ids or '-'}, "
        f"офферы скрыты: {offer_hidden_ids or '-'}, удалено direct_stock остатков: {removed_leftovers}. "
        f"Причина fallback: {fallback_reason}. Snapshot: {export_result.file_path}"
    )


def add_direct_stock_payload(db: Session, *, offer_id: int, payload: str) -> ProductPool | None:
    offer = db.get(Offer, offer_id)
    if offer is None or offer.fulfillment_type != FulfillmentType.DIRECT_STOCK:
        return None
    product = ProductPool(offer_id=offer.id, payload=payload, status=ProductStatus.AVAILABLE)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def add_direct_stock_payload_batch(db: Session, *, rows: list[tuple[int, str]]) -> tuple[int, list[str]]:
    added = 0
    errors: list[str] = []
    for idx, (offer_id, payload) in enumerate(rows, start=1):
        product = add_direct_stock_payload(db, offer_id=offer_id, payload=payload)
        if product is None:
            errors.append(f"Строка {idx}: offer_id={offer_id} не найден или не direct_stock")
            continue
        added += 1
    return added, errors


def available_payload_count(db: Session, *, offer_id: int) -> int:
    return db.scalar(
        select(func.count(ProductPool.id)).where(
            ProductPool.offer_id == offer_id,
            ProductPool.status == ProductStatus.AVAILABLE,
            ProductPool.removed_from_pool.is_(False),
        )
    ) or 0


def list_recent_orders(db: Session, *, limit: int = 15) -> list[Order]:
    return db.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit)).all()


def update_order_status_for_manual_supplier(db: Session, *, order_id: int, new_status: OrderStatus) -> Order | None:
    order = db.get(Order, order_id)
    if order is None or order.fulfillment_type != FulfillmentType.MANUAL_SUPPLIER or order.status != OrderStatus.PROCESSING:
        return None
    if new_status not in {OrderStatus.DELIVERED, OrderStatus.CANCELED}:
        return None

    order.status = new_status
    order.fulfillment_status = FulfillmentStatus.DELIVERED if new_status == OrderStatus.DELIVERED else FulfillmentStatus.CANCELED
    db.commit()
    db.refresh(order)
    return order


def list_recent_top_up_requests(db: Session, *, limit: int = 20) -> list[TopUpRequest]:
    return db.scalars(select(TopUpRequest).order_by(TopUpRequest.created_at.desc()).limit(limit)).all()


def update_user_balance_by_telegram_id(
    db: Session,
    *,
    telegram_id: int,
    action: str,
    amount: Decimal,
) -> tuple[bool, str, Decimal | None, Decimal | None]:
    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        return False, "Пользователь не найден", None, None
    old_balance = user.balance
    if action == "set":
        new_balance = amount
    elif action == "add":
        new_balance = old_balance + amount
    elif action == "sub":
        new_balance = old_balance - amount
        if new_balance < 0:
            return False, "Недостаточно средств: баланс не может стать отрицательным", old_balance, old_balance
    else:
        return False, "Неизвестная операция", old_balance, old_balance
    user.balance = new_balance.quantize(Decimal("0.01"))
    db.commit()
    db.refresh(user)
    return True, "Баланс обновлен", old_balance, user.balance
