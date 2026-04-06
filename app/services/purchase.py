import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
from app.models.offer import Offer
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
    offer_id: int,
    price: Decimal,
    ttl_minutes: int | None = None,
    now: datetime | None = None,
    max_attempts: int = 5,
    product_id: int | None = None,
) -> ReservationAttemptResult:
    current_time = now or datetime.utcnow()
    effective_ttl_minutes = ttl_minutes if ttl_minutes is not None else get_settings().product_reservation_ttl_minutes

    query = (
        select(ProductPool.id)
        .where(ProductPool.offer_id == offer_id, ProductPool.status == ProductStatus.AVAILABLE, ProductPool.removed_from_pool.is_(False))
        .order_by(ProductPool.id)
        .limit(max_attempts)
    )
    if product_id is not None:
        query = query.where(ProductPool.id == product_id).limit(1)

    candidate_ids = db.scalars(query).all()
    if not candidate_ids:
        return ReservationAttemptResult(ok=False, reason="no_stock_available")

    reserved_product_id: int | None = None
    had_conflict = False
    for candidate_id in candidate_ids:
        update_result = db.execute(
            update(ProductPool)
            .where(ProductPool.id == candidate_id, ProductPool.status == ProductStatus.AVAILABLE, ProductPool.removed_from_pool.is_(False))
            .values(status=ProductStatus.RESERVED)
        )
        if update_result.rowcount == 1:
            reserved_product_id = candidate_id
            break
        had_conflict = True

    if reserved_product_id is None:
        db.rollback()
        return ReservationAttemptResult(ok=False, reason="reservation_conflict" if had_conflict else "no_stock_available")

    reservation = Reservation(
        user_id=user_id,
        product_id=reserved_product_id,
        status=ReservationStatus.ACTIVE,
        reserved_until=current_time + timedelta(minutes=effective_ttl_minutes),
    )
    db.add(reservation)
    db.flush()

    offer = db.get(Offer, offer_id)
    order = Order(
        user_id=user_id,
        offer_id=offer_id,
        product_id=reserved_product_id,
        reservation_id=reservation.id,
        price=price,
        status=OrderStatus.PENDING,
        fulfillment_type=offer.fulfillment_type if offer else FulfillmentType.DIRECT_STOCK,
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
            payload={"product_id": reserved_product_id, "offer_id": offer_id},
        )
    )

    db.commit()
    db.refresh(reservation)
    db.refresh(order)
    return ReservationAttemptResult(ok=True, reason="reserved", reservation=reservation, order=order)


def create_non_stock_order_for_user(
    db: Session,
    *,
    user_id: int,
    offer_id: int,
    price: Decimal,
    fulfillment_type: FulfillmentType,
) -> OrderCreateResult:
    if fulfillment_type == FulfillmentType.DIRECT_STOCK:
        return OrderCreateResult(ok=False, reason="unsupported_for_direct_stock")

    order = Order(
        user_id=user_id,
        offer_id=offer_id,
        product_id=None,
        reservation_id=None,
        price=price,
        status=OrderStatus.PENDING,
        fulfillment_type=fulfillment_type,
        fulfillment_status=FulfillmentStatus.PENDING,
    )
    db.add(order)
    db.flush()
    db.add(
        ActivityLog(
            user_id=user_id,
            order_id=order.id,
            event_type=LogEventType.RESERVATION_CREATED,
            payload={"offer_id": offer_id, "fulfillment_type": fulfillment_type.value},
        )
    )
    db.commit()
    db.refresh(order)
    return OrderCreateResult(ok=True, reason="created", order=order)


def release_expired_reservations(db: Session, now: datetime | None = None) -> int:
    current_time = now or datetime.utcnow()
    expired = db.scalars(
        select(Reservation).where(Reservation.status == ReservationStatus.ACTIVE, Reservation.reserved_until < current_time)
    ).all()

    for reservation in expired:
        reservation.status = ReservationStatus.EXPIRED
        reservation.product.status = ProductStatus.AVAILABLE
        if reservation.order and reservation.order.status == OrderStatus.PENDING:
            reservation.order.status = OrderStatus.CANCELED

    db.commit()
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
            order.supplier_note = (
                "Оплата получена. Для завершения активации откройте сайт-активатор и вставьте CDK + token JSON."
            )
        else:
            order.status = OrderStatus.PROCESSING
            order.fulfillment_status = FulfillmentStatus.PROCESSING
            order.supplier_note = "Order sent to supplier/manual processing."
    elif new_status in {PaymentStatus.FAILED, PaymentStatus.EXPIRED}:
        order.status = OrderStatus.CANCELED
        order.fulfillment_status = FulfillmentStatus.CANCELED
        if reservation is not None:
            reservation.status = ReservationStatus.CANCELED
        if order.product is not None:
            order.product.status = ProductStatus.AVAILABLE

    if auto_commit:
        db.commit()
