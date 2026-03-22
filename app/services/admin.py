from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import FulfillmentStatus, FulfillmentType, OrderStatus, ProductStatus
from app.models.order import Order
from app.models.product_pool import ProductPool


def is_admin_telegram_id(telegram_id: int, admin_ids: set[int]) -> bool:
    return telegram_id in admin_ids


def list_categories_for_admin(db: Session) -> list[Category]:
    return db.scalars(select(Category).order_by(Category.id)).all()


def create_category(
    db: Session,
    *,
    name_ru: str,
    name_en: str,
    description_ru: str | None,
    description_en: str | None,
    fulfillment_type: FulfillmentType,
    base_price: Decimal | None,
) -> Category:
    category = Category(
        name_ru=name_ru,
        name_en=name_en,
        description_ru=description_ru,
        description_en=description_en,
        fulfillment_type=fulfillment_type,
        base_price=base_price,
        is_active=True,
    )
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


def update_category_price(db: Session, *, category_id: int, price: Decimal) -> Category | None:
    category = db.get(Category, category_id)
    if category is None:
        return None
    category.base_price = price
    db.commit()
    db.refresh(category)
    return category


def add_direct_stock_payload(db: Session, *, category_id: int, payload: str) -> ProductPool | None:
    category = db.get(Category, category_id)
    if category is None or category.fulfillment_type != FulfillmentType.DIRECT_STOCK:
        return None
    product = ProductPool(category_id=category.id, payload=payload, status=ProductStatus.AVAILABLE)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def available_payload_count(db: Session, *, category_id: int) -> int:
    return db.scalar(
        select(func.count(ProductPool.id)).where(ProductPool.category_id == category_id, ProductPool.status == ProductStatus.AVAILABLE)
    ) or 0


def list_recent_orders(db: Session, *, limit: int = 15) -> list[Order]:
    return db.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit)).all()


def update_order_status_for_manual_supplier(db: Session, *, order_id: int, new_status: OrderStatus) -> Order | None:
    order = db.get(Order, order_id)
    if order is None:
        return None
    if order.fulfillment_type != FulfillmentType.MANUAL_SUPPLIER:
        return None
    if order.status != OrderStatus.PROCESSING:
        return None
    if new_status not in {OrderStatus.DELIVERED, OrderStatus.CANCELED}:
        return None

    order.status = new_status
    if new_status == OrderStatus.DELIVERED:
        order.fulfillment_status = FulfillmentStatus.DELIVERED
    else:
        order.fulfillment_status = FulfillmentStatus.CANCELED
    db.commit()
    db.refresh(order)
    return order
