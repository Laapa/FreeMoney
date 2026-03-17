from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.enums import (
    LogEventType,
    OrderStatus,
    PaymentStatus,
    ProductStatus,
    ReservationStatus,
)
from app.models.order import Order
from app.models.payment import Payment
from app.models.product_pool import ProductPool
from app.models.reservation import Reservation


@dataclass(slots=True)
class ReservationAttemptResult:
    ok: bool
    reason: str
    reservation: Reservation | None = None
    order: Order | None = None



def reserve_product_for_user(
    db: Session,
    *,
    user_id: int,
    category_id: int,
    price: Decimal,
    ttl_minutes: int = 15,
    now: datetime | None = None,
    max_attempts: int = 5,
) -> ReservationAttemptResult:
    current_time = now or datetime.utcnow()

    candidate_ids = db.scalars(
        select(ProductPool.id)
        .where(
            ProductPool.category_id == category_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
        .order_by(ProductPool.id)
        .limit(max_attempts)
    ).all()

    if not candidate_ids:
        return ReservationAttemptResult(ok=False, reason="no_stock_available")

    reserved_product_id: int | None = None
    had_conflict = False

    for candidate_id in candidate_ids:
        update_result = db.execute(
            update(ProductPool)
            .where(
                ProductPool.id == candidate_id,
                ProductPool.status == ProductStatus.AVAILABLE,
            )
            .values(status=ProductStatus.RESERVED)
        )
        if update_result.rowcount == 1:
            reserved_product_id = candidate_id
            break
        had_conflict = True

    if reserved_product_id is None:
        db.rollback()
        return ReservationAttemptResult(
            ok=False,
            reason="reservation_conflict" if had_conflict else "no_stock_available",
        )

    reservation = Reservation(
        user_id=user_id,
        product_id=reserved_product_id,
        status=ReservationStatus.ACTIVE,
        reserved_until=current_time + timedelta(minutes=ttl_minutes),
    )
    db.add(reservation)
    db.flush()

    order = Order(
        user_id=user_id,
        product_id=reserved_product_id,
        reservation_id=reservation.id,
        price=price,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    db.flush()
    db.add(
        ActivityLog(
            user_id=user_id,
            reservation_id=reservation.id,
            order_id=order.id,
            event_type=LogEventType.RESERVATION_CREATED,
            payload={"product_id": reserved_product_id, "category_id": category_id},
        )
    )

    db.commit()
    db.refresh(reservation)
    db.refresh(order)
    return ReservationAttemptResult(ok=True, reason="reserved", reservation=reservation, order=order)



def release_expired_reservations(db: Session, now: datetime | None = None) -> int:
    current_time = now or datetime.utcnow()
    stmt = select(Reservation).where(
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.reserved_until < current_time,
    )
    expired = db.scalars(stmt).all()

    for reservation in expired:
        reservation.status = ReservationStatus.EXPIRED
        reservation.product.status = ProductStatus.AVAILABLE
        if reservation.order and reservation.order.status == OrderStatus.PENDING:
            reservation.order.status = OrderStatus.CANCELED
        db.add(
            ActivityLog(
                user_id=reservation.user_id,
                reservation_id=reservation.id,
                order_id=reservation.order.id if reservation.order else None,
                event_type=LogEventType.RESERVATION_EXPIRED,
                payload={"product_id": reservation.product_id},
            )
        )

    db.commit()
    return len(expired)



def apply_payment_status(db: Session, payment: Payment, new_status: PaymentStatus) -> None:
    payment.status = new_status
    order: Order = payment.order
    reservation = order.reservation

    if new_status == PaymentStatus.SUCCESS:
        order.status = OrderStatus.PAID
        reservation.status = ReservationStatus.CONVERTED
        order.product.status = ProductStatus.SOLD
        order.delivered_payload = order.product.payload
        order.delivered_at = datetime.utcnow()
        order.status = OrderStatus.DELIVERED
        db.add(
            ActivityLog(
                user_id=order.user_id,
                order_id=order.id,
                reservation_id=reservation.id,
                event_type=LogEventType.SALE_COMPLETED,
                payload={"product_id": order.product_id, "payment_id": payment.id},
            )
        )
        db.add(
            ActivityLog(
                user_id=order.user_id,
                order_id=order.id,
                reservation_id=reservation.id,
                event_type=LogEventType.DELIVERY_COMPLETED,
                payload={"product_id": order.product_id, "payment_id": payment.id},
            )
        )
    elif new_status in {PaymentStatus.FAILED, PaymentStatus.EXPIRED}:
        order.status = OrderStatus.CANCELED
        reservation.status = ReservationStatus.CANCELED
        order.product.status = ProductStatus.AVAILABLE
        db.add(
            ActivityLog(
                user_id=order.user_id,
                order_id=order.id,
                reservation_id=reservation.id,
                event_type=LogEventType.PAYMENT_FAILED,
                payload={"product_id": order.product_id, "payment_id": payment.id, "status": new_status.value},
            )
        )

    db.commit()
