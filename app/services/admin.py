from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import FulfillmentStatus, FulfillmentType, OrderStatus, ProductStatus
from app.models.offer import Offer
from app.models.order import Order
from app.models.product_pool import ProductPool
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.admin_exports import can_delete_category, can_delete_offer, export_category_snapshot, export_offer_snapshot


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


def export_offer(db: Session, *, offer_id: int, reason: str) -> tuple[Offer | None, str | None]:
    offer = db.get(Offer, offer_id)
    if offer is None:
        return None, None
    result = export_offer_snapshot(db, offer=offer, reason=reason)
    return offer, str(result.file_path)


def delete_offer(db: Session, *, offer_id: int) -> tuple[bool, str]:
    offer = db.get(Offer, offer_id)
    if offer is None:
        return False, "Товар не найден"
    export_result = export_offer_snapshot(db, offer=offer, reason="delete_offer")
    allowed, reason = can_delete_offer(db, offer_id=offer_id)
    if not allowed:
        return False, f"{reason}. Snapshot: {export_result.file_path}"
    db.delete(offer)
    db.commit()
    return True, f"Товар удален. Snapshot: {export_result.file_path}"


def export_category(db: Session, *, category_id: int, reason: str) -> tuple[Category | None, str | None]:
    category = db.get(Category, category_id)
    if category is None:
        return None, None
    result = export_category_snapshot(db, category=category, reason=reason)
    return category, str(result.file_path)


def delete_category(db: Session, *, category_id: int) -> tuple[bool, str]:
    category = db.get(Category, category_id)
    if category is None:
        return False, "Категория не найдена"
    export_result = export_category_snapshot(db, category=category, reason="delete_category")
    allowed, reason = can_delete_category(db, category_id=category_id)
    if not allowed:
        return False, f"{reason}. Snapshot: {export_result.file_path}"
    db.delete(category)
    db.commit()
    return True, f"Категория удалена. Snapshot: {export_result.file_path}"


def add_direct_stock_payload(db: Session, *, offer_id: int, payload: str) -> ProductPool | None:
    offer = db.get(Offer, offer_id)
    if offer is None or offer.fulfillment_type != FulfillmentType.DIRECT_STOCK:
        return None
    product = ProductPool(offer_id=offer.id, payload=payload, status=ProductStatus.AVAILABLE)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def available_payload_count(db: Session, *, offer_id: int) -> int:
    return db.scalar(select(func.count(ProductPool.id)).where(ProductPool.offer_id == offer_id, ProductPool.status == ProductStatus.AVAILABLE)) or 0


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
