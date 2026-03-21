from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import PaymentMethod, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.services.purchase import apply_payment_status


@dataclass(frozen=True)
class PaymentCreateResult:
    ok: bool
    reason: str
    payment: Payment | None = None


@dataclass(frozen=True)
class PaymentCheckResult:
    ok: bool
    reason: str
    payment: Payment | None = None


def create_order_payment(
    db: Session,
    *,
    order: Order,
    method: PaymentMethod = PaymentMethod.TEST_STUB,
    now: datetime | None = None,
    ttl_minutes: int = 30,
) -> PaymentCreateResult:
    if order.payment is not None and order.payment.status in {PaymentStatus.PENDING, PaymentStatus.SUCCESS}:
        return PaymentCreateResult(ok=False, reason="payment_already_exists", payment=order.payment)

    current_time = now or datetime.utcnow()
    payment = order.payment
    if payment is None:
        payment = Payment(order_id=order.id, amount=Decimal(order.price), method=method, provider=method.value)
        db.add(payment)
    else:
        payment.method = method
        payment.provider = method.value
        payment.amount = Decimal(order.price)

    payment.status = PaymentStatus.PENDING
    payment.provider_payment_id = f"{method.value}-{order.id}-{int(current_time.timestamp())}"
    payment.expires_at = current_time + timedelta(minutes=ttl_minutes)
    db.commit()
    db.refresh(payment)
    return PaymentCreateResult(ok=True, reason="payment_created", payment=payment)


def check_order_payment(db: Session, *, order: Order, now: datetime | None = None, test_confirm: bool = True) -> PaymentCheckResult:
    payment = order.payment
    if payment is None:
        return PaymentCheckResult(ok=False, reason="payment_not_found")

    current_time = now or datetime.utcnow()
    if payment.status == PaymentStatus.SUCCESS:
        return PaymentCheckResult(ok=True, reason="already_paid", payment=payment)

    if payment.expires_at and payment.expires_at < current_time:
        apply_payment_status(db, payment, PaymentStatus.EXPIRED, now=current_time)
        return PaymentCheckResult(ok=False, reason="payment_expired", payment=payment)

    if payment.method == PaymentMethod.TEST_STUB and test_confirm:
        apply_payment_status(db, payment, PaymentStatus.SUCCESS, now=current_time)
        db.refresh(payment)
        return PaymentCheckResult(ok=True, reason="test_confirmed", payment=payment)

    return PaymentCheckResult(ok=False, reason="payment_pending", payment=payment)


def cancel_order_payment(db: Session, *, order: Order, now: datetime | None = None) -> PaymentCheckResult:
    payment = order.payment
    if payment is None:
        return PaymentCheckResult(ok=False, reason="payment_not_found")
    if payment.status in {PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.EXPIRED}:
        return PaymentCheckResult(ok=False, reason="payment_not_cancelable", payment=payment)

    apply_payment_status(db, payment, PaymentStatus.FAILED, now=now)
    db.refresh(payment)
    return PaymentCheckResult(ok=True, reason="payment_canceled", payment=payment)
