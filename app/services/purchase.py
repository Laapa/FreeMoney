import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.enums import (
    FulfillmentStatus,
    FulfillmentType,
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

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ReservationAttemptResult:
    ok: bool
    reason: str
    reservation: Reservation | None = None
    order: Order | None = None


@dataclass(slots=True)
class OrderCreateResult:
    ok: bool
    reason: str
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
    product_id: int | None = None,
) -> ReservationAttemptResult:
    current_time = now or datetime.utcnow()

    query = (
        select(ProductPool.id)
        .where(
            ProductPool.category_id == category_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
        .order_by(ProductPool.id)
        .limit(max_attempts)
    )
    if product_id is not None:
        query = query.where(ProductPool.id == product_id).limit(1)

    candidate_ids = db.scalars(query).all()

    if not candidate_ids:
        logger.info("Reservation failed: no stock | user_id=%s category_id=%s", user_id, category_id)
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
        logger.warning("Reservation conflict | user_id=%s category_id=%s", user_id, category_id)
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
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        fulfillment_status=FulfillmentStatus.PENDING,
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
    logger.info(
        "Reservation created | user_id=%s category_id=%s reservation_id=%s order_id=%s",
        user_id,
        category_id,
        reservation.id,
        order.id,
    )
    return ReservationAttemptResult(ok=True, reason="reserved", reservation=reservation, order=order)


def create_non_stock_order_for_user(
    db: Session,
    *,
    user_id: int,
    category_id: int,
    price: Decimal,
    fulfillment_type: FulfillmentType,
) -> OrderCreateResult:
    if fulfillment_type == FulfillmentType.DIRECT_STOCK:
        return OrderCreateResult(ok=False, reason="unsupported_for_direct_stock")

    order = Order(
        user_id=user_id,
        product_id=None,
        reservation_id=None,
        price=price,
        status=OrderStatus.PENDING,
        fulfillment_type=fulfillment_type,
        fulfillment_status=FulfillmentStatus.PENDING,
    )
    db.add(order)
    db.add(
        ActivityLog(
            user_id=user_id,
            order_id=order.id,
            event_type=LogEventType.RESERVATION_CREATED,
            payload={"category_id": category_id, "fulfillment_type": fulfillment_type.value},
        )
    )
    db.commit()
    db.refresh(order)
    return OrderCreateResult(ok=True, reason="created", order=order)


def release_expired_reservations(db: Session, now: datetime | None = None) -> int:
    current_time = now or datetime.utcnow()
    expired = db.scalars(
        select(Reservation).where(
            Reservation.status == ReservationStatus.ACTIVE,
            Reservation.reserved_until < current_time,
        )
    ).all()

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
    if expired:
        logger.info("Expired reservations released | count=%s", len(expired))
    return len(expired)


def apply_payment_status(
    db: Session,
    payment: Payment,
    new_status: PaymentStatus,
    *,
    now: datetime | None = None,
    auto_commit: bool = True,
) -> None:
    payment.status = new_status
    order = payment.order
    reservation = order.reservation

    if new_status == PaymentStatus.SUCCESS:
        if order.status == OrderStatus.DELIVERED and order.delivered_payload:
            if auto_commit:
                db.commit()
            return

        delivered_at = now or datetime.utcnow()
        order.status = OrderStatus.PAID
        if order.fulfillment_type == FulfillmentType.DIRECT_STOCK:
            if reservation is not None:
                reservation.status = ReservationStatus.CONVERTED
            if order.product is not None:
                order.product.status = ProductStatus.SOLD
                order.delivered_payload = order.product.payload
            order.delivered_at = delivered_at
            order.status = OrderStatus.DELIVERED
            order.fulfillment_status = FulfillmentStatus.DELIVERED
        elif order.fulfillment_type == FulfillmentType.ACTIVATION_TASK:
            order.status = OrderStatus.PROCESSING
            order.fulfillment_status = FulfillmentStatus.PROCESSING
            order.external_task_id = order.external_task_id or f"act-{order.id}"
            order.supplier_note = "Activation task created and queued."
        else:
            order.status = OrderStatus.PROCESSING
            order.fulfillment_status = FulfillmentStatus.PROCESSING
            order.supplier_note = "Order sent to supplier/manual processing."

        db.add(
            ActivityLog(
                user_id=order.user_id,
                order_id=order.id,
                reservation_id=reservation.id if reservation else None,
                event_type=LogEventType.SALE_COMPLETED,
                payload={"product_id": order.product_id, "payment_id": payment.id},
            )
        )
        if order.fulfillment_status == FulfillmentStatus.DELIVERED:
            db.add(
                ActivityLog(
                    user_id=order.user_id,
                    order_id=order.id,
                    reservation_id=reservation.id if reservation else None,
                    event_type=LogEventType.DELIVERY_COMPLETED,
                    payload={"product_id": order.product_id, "payment_id": payment.id},
                )
            )
        logger.info("Payment success processed | order_id=%s payment_id=%s", order.id, payment.id)
    elif new_status in {PaymentStatus.FAILED, PaymentStatus.EXPIRED}:
        order.status = OrderStatus.CANCELED
        order.fulfillment_status = FulfillmentStatus.CANCELED
        if reservation is not None:
            reservation.status = ReservationStatus.CANCELED
        if order.product is not None:
            order.product.status = ProductStatus.AVAILABLE
        db.add(
            ActivityLog(
                user_id=order.user_id,
                order_id=order.id,
                reservation_id=reservation.id if reservation else None,
                event_type=LogEventType.PAYMENT_FAILED,
                payload={"product_id": order.product_id, "payment_id": payment.id, "status": new_status.value},
            )
        )
        logger.warning("Payment failed/expired | order_id=%s payment_id=%s status=%s", order.id, payment.id, new_status.value)

    if auto_commit:
        db.commit()
