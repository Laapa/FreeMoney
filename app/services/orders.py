from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.enums import OrderStatus, PaymentStatus, ReservationStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.reservation import Reservation
from app.models.user import User
from app.services.purchase import apply_payment_status


@dataclass(frozen=True)
class UserOrderStats:
    total_orders: int
    delivered_orders: int
    total_spent: Decimal


@dataclass(frozen=True)
class OrderPaymentResult:
    ok: bool
    reason: str
    order: Order | None = None
    payment: Payment | None = None


def list_user_orders(db: Session, *, user_id: int, limit: int = 5, offset: int = 0) -> list[Order]:
    return db.scalars(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()


def get_user_order(db: Session, *, user_id: int, order_id: int) -> Order | None:
    return db.scalar(select(Order).where(Order.user_id == user_id, Order.id == order_id))


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


def pay_pending_order_from_balance(db: Session, *, user_id: int, order_id: int, now: datetime | None = None) -> OrderPaymentResult:
    order = get_user_order(db, user_id=user_id, order_id=order_id)
    if order is None:
        return OrderPaymentResult(ok=False, reason="order_not_found")

    if order.status == OrderStatus.DELIVERED:
        return OrderPaymentResult(ok=False, reason="already_delivered", order=order)
    if order.status == OrderStatus.PAID:
        return OrderPaymentResult(ok=False, reason="already_paid", order=order)
    if order.status == OrderStatus.CANCELED:
        return OrderPaymentResult(ok=False, reason="order_canceled", order=order)
    if order.status != OrderStatus.PENDING:
        return OrderPaymentResult(ok=False, reason="order_not_payable", order=order)

    reservation = db.get(Reservation, order.reservation_id)
    if reservation is None or reservation.status != ReservationStatus.ACTIVE:
        return OrderPaymentResult(ok=False, reason="reservation_not_active", order=order)

    balance_updated = db.execute(
        update(User)
        .where(User.id == user_id, User.balance >= order.price)
        .values(balance=User.balance - order.price)
    )
    if balance_updated.rowcount != 1:
        db.rollback()
        return OrderPaymentResult(ok=False, reason="insufficient_balance", order=order)

    payment = order.payment
    if payment is not None and payment.status == PaymentStatus.SUCCESS:
        db.rollback()
        return OrderPaymentResult(ok=False, reason="already_paid", order=order, payment=payment)

    if payment is None:
        payment = Payment(order_id=order.id, amount=order.price, status=PaymentStatus.CREATED)
        db.add(payment)
        db.flush()
    else:
        payment.amount = order.price

    apply_payment_status(db, payment, PaymentStatus.SUCCESS, now=now, auto_commit=False)
    db.commit()
    db.refresh(order)
    db.refresh(payment)
    return OrderPaymentResult(ok=True, reason="paid_and_delivered", order=order, payment=payment)
