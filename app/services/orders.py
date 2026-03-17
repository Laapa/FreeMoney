from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import OrderStatus
from app.models.order import Order


@dataclass(frozen=True)
class UserOrderStats:
    total_orders: int
    delivered_orders: int
    total_spent: Decimal


def list_user_orders(db: Session, *, user_id: int, limit: int = 5, offset: int = 0) -> list[Order]:
    return db.scalars(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()


def count_user_orders(db: Session, *, user_id: int) -> int:
    return db.scalar(select(func.count(Order.id)).where(Order.user_id == user_id)) or 0


def get_user_order_stats(db: Session, *, user_id: int) -> UserOrderStats:
    total_orders = count_user_orders(db, user_id=user_id)
    delivered_orders = db.scalar(
        select(func.count(Order.id)).where(Order.user_id == user_id, Order.status == OrderStatus.DELIVERED)
    ) or 0
    total_spent = db.scalar(
        select(func.coalesce(func.sum(Order.price), 0)).where(
            Order.user_id == user_id,
            Order.status.in_([OrderStatus.PAID, OrderStatus.DELIVERED]),
        )
    )
    if not isinstance(total_spent, Decimal):
        total_spent = Decimal(str(total_spent))

    return UserOrderStats(
        total_orders=total_orders,
        delivered_orders=delivered_orders,
        total_spent=total_spent,
    )
