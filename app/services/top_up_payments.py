from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.activity_log import ActivityLog
from app.models.enums import LogEventType, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.crypto_pay import CryptoPayClient, CryptoPayClientError
from app.services.fees import quantize_money

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopUpPaymentResult:
    ok: bool
    reason: str
    request: TopUpRequest | None = None


def create_crypto_pay_top_up_invoice(
    db: Session,
    *,
    request_id: int,
    crypto_pay_client: CryptoPayClient | None = None,
) -> TopUpPaymentResult:
    request = db.scalar(select(TopUpRequest).where(TopUpRequest.id == request_id).with_for_update())
    if request is None:
        return TopUpPaymentResult(ok=False, reason="request_not_found")
    if request.method != TopUpMethod.CRYPTO_PAY:
        return TopUpPaymentResult(ok=False, reason="invalid_method", request=request)
    if request.provider_payment_url and request.provider_payment_id:
        return TopUpPaymentResult(ok=True, reason="invoice_exists", request=request)

    settings = get_settings()
    token = settings.cryptopay_api_token
    if not token:
        return TopUpPaymentResult(ok=False, reason="cryptopay_not_configured", request=request)

    client = crypto_pay_client or CryptoPayClient(
        api_token=token,
        base_url=settings.cryptopay_effective_api_base_url,
    )
    try:
        invoice = client.create_invoice(
            amount=request.gross_amount,
            asset=settings.cryptopay_asset,
            expires_in=settings.cryptopay_invoice_expires_in,
        )
    except CryptoPayClientError:
        logger.exception("CryptoPay top-up invoice create failed | request_id=%s", request.id)
        return TopUpPaymentResult(ok=False, reason="cryptopay_unavailable", request=request)

    request.provider_payment_id = invoice.invoice_id
    request.provider_status = invoice.status
    request.last_auto_verify_attempt_at = datetime.utcnow()
    request.provider_payment_url = invoice.pay_url
    request.provider_invoice_url = invoice.bot_invoice_url
    request.external_reference = request.external_reference or invoice.invoice_id
    db.commit()
    db.refresh(request)
    return TopUpPaymentResult(ok=True, reason="invoice_created", request=request)


def check_crypto_pay_top_up(
    db: Session,
    *,
    request_id: int,
    crypto_pay_client: CryptoPayClient | None = None,
) -> TopUpPaymentResult:
    request = db.scalar(select(TopUpRequest).where(TopUpRequest.id == request_id).with_for_update())
    if request is None:
        return TopUpPaymentResult(ok=False, reason="request_not_found")
    if request.method != TopUpMethod.CRYPTO_PAY:
        return TopUpPaymentResult(ok=False, reason="invalid_method", request=request)
    if request.status == TopUpStatus.VERIFIED or request.credited_at is not None:
        return TopUpPaymentResult(ok=True, reason="already_credited", request=request)
    if not request.provider_payment_id:
        return TopUpPaymentResult(ok=False, reason="invoice_missing", request=request)

    settings = get_settings()
    token = settings.cryptopay_api_token
    if not token:
        return TopUpPaymentResult(ok=False, reason="cryptopay_not_configured", request=request)

    client = crypto_pay_client or CryptoPayClient(
        api_token=token,
        base_url=settings.cryptopay_effective_api_base_url,
    )
    try:
        invoices = client.get_invoices(invoice_ids=[request.provider_payment_id])
    except CryptoPayClientError:
        logger.exception("CryptoPay top-up invoice check failed | request_id=%s", request.id)
        return TopUpPaymentResult(ok=False, reason="cryptopay_unavailable", request=request)

    if not invoices:
        return TopUpPaymentResult(ok=False, reason="invoice_not_found", request=request)

    invoice = invoices[0]
    request.provider_status = invoice.status
    request.last_auto_verify_attempt_at = datetime.utcnow()
    request.provider_payment_url = request.provider_payment_url or invoice.pay_url
    request.provider_invoice_url = request.provider_invoice_url or invoice.bot_invoice_url

    if invoice.status == "paid":
        request.last_auto_verify_note = "matched"
        _credit_top_up_request(db, request=request, note="Auto-verified by Crypto Pay invoice status=paid")
        return TopUpPaymentResult(ok=True, reason="credited", request=request)

    if invoice.status in {"expired", "invalid"}:
        request.last_auto_verify_note = f"invoice_{invoice.status}"
        request.status = TopUpStatus.EXPIRED
        db.commit()
        db.refresh(request)
        return TopUpPaymentResult(ok=False, reason=f"invoice_{invoice.status}", request=request)

    request.last_auto_verify_note = "payment_pending"
    db.commit()
    db.refresh(request)
    return TopUpPaymentResult(ok=False, reason="payment_pending", request=request)


def _credit_top_up_request(db: Session, *, request: TopUpRequest, note: str) -> None:
    if request.credited_at is not None:
        db.refresh(request)
        return
    user = db.scalar(select(User).where(User.id == request.user_id).with_for_update())
    if user is None:
        raise ValueError("Top-up user not found")

    now = datetime.utcnow()
    request.status = TopUpStatus.VERIFIED
    request.reviewed_at = now
    request.verification_note = note
    request.verification_source = "auto_cryptopay"
    request.credited_at = now
    user.balance = quantize_money(user.balance + request.net_amount)

    db.add(
        ActivityLog(
            user_id=request.user_id,
            event_type=LogEventType.TOP_UP_VERIFIED,
            payload={
                "top_up_request_id": request.id,
                "method": request.method.value,
                "status": request.status.value,
                "net_amount": str(request.net_amount),
                "fee_amount": str(request.fee_amount),
                "gross_amount": str(request.gross_amount),
                "provider_payment_id": request.provider_payment_id,
                "provider_status": request.provider_status,
                "credited_at": request.credited_at.isoformat(),
            },
        )
    )
    db.commit()
    db.refresh(request)
