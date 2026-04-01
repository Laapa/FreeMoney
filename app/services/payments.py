from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus, ReservationStatus
from app.models.order import Order
from app.models.payment import Payment
from app.services.crypto_pay import CryptoPayClient, CryptoPayClientError
from app.services.purchase import apply_payment_status, release_expired_reservations
from app.services.fees import calculate_external_fee
from app.activation.client import ActivationAPIClient

logger = logging.getLogger(__name__)


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
    crypto_pay_client: CryptoPayClient | None = None,
) -> PaymentCreateResult:
    if order.reservation_id is not None:
        release_expired_reservations(db, now=now)
        db.refresh(order)
        if order.status != OrderStatus.PENDING:
            return PaymentCreateResult(ok=False, reason=f"order_not_payable:{order.status.value}", payment=order.payment)
        if order.reservation is None or order.reservation.status != ReservationStatus.ACTIVE:
            return PaymentCreateResult(ok=False, reason="reservation_not_active", payment=order.payment)

    if order.status != OrderStatus.PENDING:
        return PaymentCreateResult(ok=False, reason=f"order_not_payable:{order.status.value}", payment=order.payment)

    if order.payment is not None and order.payment.status in {PaymentStatus.PENDING, PaymentStatus.SUCCESS}:
        return PaymentCreateResult(ok=False, reason="payment_already_exists", payment=order.payment)

    current_time = now or datetime.utcnow()
    payment = order.payment
    if payment is None:
        fee = calculate_external_fee(Decimal(order.price))
        payment = Payment(
            order_id=order.id,
            amount=fee.gross_amount,
            net_amount=fee.net_amount,
            fee_amount=fee.fee_amount,
            gross_amount=fee.gross_amount,
            method=method,
            provider=method.value,
        )
        db.add(payment)
    else:
        fee = calculate_external_fee(Decimal(order.price))
        payment.method = method
        payment.provider = method.value
        payment.amount = fee.gross_amount
        payment.net_amount = fee.net_amount
        payment.fee_amount = fee.fee_amount
        payment.gross_amount = fee.gross_amount

    payment.status = PaymentStatus.PENDING
    if method == PaymentMethod.CRYPTO_PAY:
        settings = get_settings()
        token = settings.cryptopay_api_token
        if not token:
            return PaymentCreateResult(ok=False, reason="cryptopay_not_configured", payment=payment)
        client = crypto_pay_client or CryptoPayClient(
            api_token=token,
            base_url=settings.cryptopay_effective_api_base_url,
        )
        try:
            invoice = client.create_invoice(
                amount=payment.gross_amount,
                asset=settings.cryptopay_asset,
                expires_in=settings.cryptopay_invoice_expires_in,
            )
        except CryptoPayClientError as exc:
            logger.warning("Crypto Pay invoice create failed | order_id=%s error=%s", order.id, str(exc))
            db.rollback()
            return PaymentCreateResult(ok=False, reason="cryptopay_unavailable")

        payment.provider_payment_id = invoice.invoice_id
        payment.provider_status = invoice.status
        payment.provider_payment_url = invoice.pay_url
        payment.provider_invoice_url = invoice.bot_invoice_url
        payment.expires_at = invoice.expires_at or (current_time + timedelta(minutes=ttl_minutes))
    else:
        payment.provider_payment_id = f"{method.value}-{order.id}-{int(current_time.timestamp())}"
        payment.expires_at = current_time + timedelta(minutes=ttl_minutes)

    db.commit()
    db.refresh(payment)
    return PaymentCreateResult(ok=True, reason="payment_created", payment=payment)


def check_order_payment(
    db: Session,
    *,
    order: Order,
    now: datetime | None = None,
    test_confirm: bool = True,
    crypto_pay_client: CryptoPayClient | None = None,
    activation_client: ActivationAPIClient | None = None,
) -> PaymentCheckResult:
    if order.reservation_id is not None:
        release_expired_reservations(db, now=now)
        db.refresh(order)
        if order.status != OrderStatus.PENDING:
            return PaymentCheckResult(ok=False, reason=f"order_not_payable:{order.status.value}", payment=order.payment)
        if order.reservation is None or order.reservation.status != ReservationStatus.ACTIVE:
            return PaymentCheckResult(ok=False, reason="reservation_not_active", payment=order.payment)

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
    if payment.method == PaymentMethod.CRYPTO_PAY:
        settings = get_settings()
        token = settings.cryptopay_api_token
        if not token:
            return PaymentCheckResult(ok=False, reason="cryptopay_not_configured", payment=payment)
        if not payment.provider_payment_id:
            return PaymentCheckResult(ok=False, reason="invoice_missing", payment=payment)
        client = crypto_pay_client or CryptoPayClient(
            api_token=token,
            base_url=settings.cryptopay_effective_api_base_url,
        )
        try:
            invoices = client.get_invoices(invoice_ids=[payment.provider_payment_id])
        except CryptoPayClientError as exc:
            logger.warning("Crypto Pay invoice check failed | payment_id=%s error=%s", payment.id, str(exc))
            return PaymentCheckResult(ok=False, reason="cryptopay_unavailable", payment=payment)
        if not invoices:
            return PaymentCheckResult(ok=False, reason="invoice_not_found", payment=payment)
        invoice = invoices[0]
        payment.provider_status = invoice.status
        payment.provider_payment_url = payment.provider_payment_url or invoice.pay_url
        payment.provider_invoice_url = payment.provider_invoice_url or invoice.bot_invoice_url
        if invoice.expires_at:
            payment.expires_at = invoice.expires_at
        if invoice.status == "paid":
            apply_payment_status(db, payment, PaymentStatus.SUCCESS, now=current_time, auto_commit=False)
            db.commit()
            db.refresh(payment)
            return PaymentCheckResult(ok=True, reason="cryptopay_paid", payment=payment)
        if invoice.status == "active":
            db.commit()
            db.refresh(payment)
            return PaymentCheckResult(ok=False, reason="payment_pending", payment=payment)
        if invoice.status in {"expired", "invalid"}:
            apply_payment_status(db, payment, PaymentStatus.EXPIRED, now=current_time, auto_commit=False)
            db.commit()
            db.refresh(payment)
            return PaymentCheckResult(ok=False, reason=f"invoice_{invoice.status}", payment=payment)
        db.commit()
        db.refresh(payment)
        return PaymentCheckResult(ok=False, reason=f"invoice_{invoice.status}", payment=payment)

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
