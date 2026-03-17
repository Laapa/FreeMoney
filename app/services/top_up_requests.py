from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.enums import Currency, LogEventType, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.services.top_up_statuses import TopUpRequestTransitionError, ensure_top_up_status_transition


def create_top_up_request(
    db: Session,
    *,
    user_id: int,
    method: TopUpMethod,
    amount: Decimal,
    currency: Currency,
    external_reference: str | None = None,
) -> TopUpRequest:
    initial_status = TopUpStatus.WAITING_TXID if method == TopUpMethod.CRYPTO_TXID else TopUpStatus.PENDING
    request = TopUpRequest(
        user_id=user_id,
        method=method,
        amount=amount,
        currency=currency,
        status=initial_status,
        external_reference=external_reference,
    )
    db.add(request)
    db.flush()

    db.add(
        ActivityLog(
            user_id=user_id,
            event_type=LogEventType.TOP_UP_REQUEST_CREATED,
            payload={
                "top_up_request_id": request.id,
                "method": request.method.value,
                "amount": str(request.amount),
                "currency": request.currency.value,
                "status": request.status.value,
            },
        )
    )

    db.commit()
    db.refresh(request)
    return request


def set_top_up_txid(db: Session, *, request: TopUpRequest, txid: str) -> TopUpRequest:
    if request.method != TopUpMethod.CRYPTO_TXID:
        raise TopUpRequestTransitionError(
            f"Cannot set txid for method '{request.method.value}', expected '{TopUpMethod.CRYPTO_TXID.value}'"
        )
    if request.status != TopUpStatus.WAITING_TXID:
        raise TopUpRequestTransitionError(
            f"Cannot set txid for request in status '{request.status.value}', expected '{TopUpStatus.WAITING_TXID.value}'"
        )
    if request.txid is not None:
        raise TopUpRequestTransitionError("Cannot overwrite txid for this top-up request")

    ensure_top_up_status_transition(request, TopUpStatus.WAITING_VERIFICATION)
    request.txid = txid
    request.status = TopUpStatus.WAITING_VERIFICATION

    db.add(
        ActivityLog(
            user_id=request.user_id,
            event_type=LogEventType.TOP_UP_WAITING_VERIFICATION,
            payload={
                "top_up_request_id": request.id,
                "method": request.method.value,
                "status": request.status.value,
            },
        )
    )

    db.commit()
    db.refresh(request)
    return request


def set_top_up_waiting_verification(db: Session, *, request: TopUpRequest, reference: str | None = None) -> TopUpRequest:
    ensure_top_up_status_transition(request, TopUpStatus.WAITING_VERIFICATION)
    request.status = TopUpStatus.WAITING_VERIFICATION
    if reference:
        request.external_reference = reference

    db.add(
        ActivityLog(
            user_id=request.user_id,
            event_type=LogEventType.TOP_UP_WAITING_VERIFICATION,
            payload={
                "top_up_request_id": request.id,
                "method": request.method.value,
                "status": request.status.value,
                "reference": reference,
            },
        )
    )

    db.commit()
    db.refresh(request)
    return request


def get_top_up_request(db: Session, *, request_id: int, user_id: int) -> TopUpRequest | None:
    return db.scalar(select(TopUpRequest).where(TopUpRequest.id == request_id, TopUpRequest.user_id == user_id))


def list_user_top_up_requests(db: Session, *, user_id: int, limit: int = 5) -> list[TopUpRequest]:
    statement = (
        select(TopUpRequest)
        .where(TopUpRequest.user_id == user_id)
        .order_by(TopUpRequest.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())
