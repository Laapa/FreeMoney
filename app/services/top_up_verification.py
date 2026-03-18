from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.enums import LogEventType, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.top_up_statuses import TopUpRequestTransitionError, ensure_top_up_status_transition


class TopUpVerificationError(str, Enum):
    REQUEST_NOT_FOUND = "request_not_found"
    ACCESS_DENIED = "access_denied"
    INVALID_METHOD = "invalid_method"
    TXID_MISSING = "txid_missing"
    INVALID_SOURCE_STATUS = "invalid_source_status"
    INVALID_TARGET_STATUS = "invalid_target_status"
    ALREADY_CREDITED = "already_credited"
    PAYMENT_REFERENCE_MISSING = "payment_reference_missing"


@dataclass(frozen=True)
class TopUpVerificationResult:
    ok: bool
    request: TopUpRequest | None = None
    error: TopUpVerificationError | None = None


_ALLOWED_TARGET_STATUSES = {
    TopUpStatus.VERIFIED,
    TopUpStatus.REJECTED,
    TopUpStatus.EXPIRED,
}


def verify_crypto_txid_top_up(
    db: Session,
    *,
    request_id: int,
    target_status: TopUpStatus,
    reviewed_by_user_id: int | None = None,
    verification_note: str | None = None,
) -> TopUpVerificationResult:
    if target_status not in _ALLOWED_TARGET_STATUSES:
        return TopUpVerificationResult(ok=False, error=TopUpVerificationError.INVALID_TARGET_STATUS)

    request = db.scalar(select(TopUpRequest).where(TopUpRequest.id == request_id).with_for_update())
    if request is None:
        return TopUpVerificationResult(ok=False, error=TopUpVerificationError.REQUEST_NOT_FOUND)

    if reviewed_by_user_id is not None and request.user_id != reviewed_by_user_id:
        return TopUpVerificationResult(ok=False, error=TopUpVerificationError.ACCESS_DENIED)

    if request.method != TopUpMethod.CRYPTO_TXID:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.INVALID_METHOD)

    if not request.txid:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.TXID_MISSING)

    if target_status == TopUpStatus.VERIFIED and request.credited_at is not None:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.ALREADY_CREDITED)

    try:
        ensure_top_up_status_transition(request, target_status)
    except TopUpRequestTransitionError:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.INVALID_SOURCE_STATUS)

    now = datetime.utcnow()
    request.status = target_status
    request.reviewed_at = now
    request.verification_note = verification_note

    event_type = LogEventType.TOP_UP_VERIFIED
    if target_status == TopUpStatus.VERIFIED:
        user = db.scalar(select(User).where(User.id == request.user_id).with_for_update())
        if user is None:
            return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.REQUEST_NOT_FOUND)
        user.balance = _money(user.balance) + _money(request.amount)
        request.credited_at = now
    elif target_status == TopUpStatus.REJECTED:
        event_type = LogEventType.TOP_UP_REJECTED
    else:
        event_type = LogEventType.TOP_UP_EXPIRED

    db.add(
        ActivityLog(
            user_id=request.user_id,
            event_type=event_type,
            payload={
                "top_up_request_id": request.id,
                "status": request.status.value,
                "amount": str(request.amount),
                "currency": request.currency.value,
                "txid": request.txid,
                "credited_at": request.credited_at.isoformat() if request.credited_at else None,
                "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None,
                "verification_note": request.verification_note,
            },
        )
    )

    db.commit()

    db.refresh(request)
    return TopUpVerificationResult(ok=True, request=request)


def verify_bybit_uid_top_up(
    db: Session,
    *,
    request_id: int,
    target_status: TopUpStatus,
    reviewed_by_user_id: int | None = None,
    verification_note: str | None = None,
) -> TopUpVerificationResult:
    if target_status not in _ALLOWED_TARGET_STATUSES:
        return TopUpVerificationResult(ok=False, error=TopUpVerificationError.INVALID_TARGET_STATUS)

    request = db.scalar(select(TopUpRequest).where(TopUpRequest.id == request_id).with_for_update())
    if request is None:
        return TopUpVerificationResult(ok=False, error=TopUpVerificationError.REQUEST_NOT_FOUND)

    if reviewed_by_user_id is not None and request.user_id != reviewed_by_user_id:
        return TopUpVerificationResult(ok=False, error=TopUpVerificationError.ACCESS_DENIED)

    if request.method != TopUpMethod.BYBIT_UID:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.INVALID_METHOD)

    if not request.sender_uid and not request.external_reference:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.PAYMENT_REFERENCE_MISSING)

    if target_status == TopUpStatus.VERIFIED and request.credited_at is not None:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.ALREADY_CREDITED)

    try:
        ensure_top_up_status_transition(request, target_status)
    except TopUpRequestTransitionError:
        return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.INVALID_SOURCE_STATUS)

    now = datetime.utcnow()
    request.status = target_status
    request.reviewed_at = now
    request.verification_note = verification_note

    event_type = LogEventType.TOP_UP_VERIFIED
    if target_status == TopUpStatus.VERIFIED:
        user = db.scalar(select(User).where(User.id == request.user_id).with_for_update())
        if user is None:
            return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.REQUEST_NOT_FOUND)
        user.balance = _money(user.balance) + _money(request.amount)
        request.credited_at = now
    elif target_status == TopUpStatus.REJECTED:
        event_type = LogEventType.TOP_UP_REJECTED
    else:
        event_type = LogEventType.TOP_UP_EXPIRED

    db.add(
        ActivityLog(
            user_id=request.user_id,
            event_type=event_type,
            payload={
                "top_up_request_id": request.id,
                "status": request.status.value,
                "amount": str(request.amount),
                "currency": request.currency.value,
                "sender_uid": request.sender_uid,
                "external_reference": request.external_reference,
                "credited_at": request.credited_at.isoformat() if request.credited_at else None,
                "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None,
                "verification_note": request.verification_note,
            },
        )
    )

    db.commit()

    db.refresh(request)
    return TopUpVerificationResult(ok=True, request=request)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
