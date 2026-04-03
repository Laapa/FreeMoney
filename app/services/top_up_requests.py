import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.enums import Currency, LogEventType, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.services.fees import FeeBreakdown
from app.services.top_up_statuses import TopUpRequestTransitionError, ensure_top_up_status_transition
from app.services.fees import calculate_external_fee

logger = logging.getLogger(__name__)


def create_top_up_request(
    db: Session,
    *,
    user_id: int,
    method: TopUpMethod,
    amount: Decimal,
    currency: Currency,
    requested_network: str | None = None,
    requested_token: str | None = None,
    external_reference: str | None = None,
) -> TopUpRequest:
    initial_status = TopUpStatus.WAITING_TXID if method == TopUpMethod.CRYPTO_TXID else TopUpStatus.PENDING
    fee = (
        FeeBreakdown(
            net_amount=amount,
            fee_amount=Decimal("0.00"),
            gross_amount=amount,
            fee_percent=Decimal("0.00"),
        )
        if method == TopUpMethod.BYBIT_UID
        else calculate_external_fee(amount)
    )
    request = TopUpRequest(
        user_id=user_id,
        method=method,
        amount=fee.net_amount,
        net_amount=fee.net_amount,
        fee_amount=fee.fee_amount,
        gross_amount=fee.gross_amount,
        currency=currency,
        status=initial_status,
        requested_network=requested_network,
        requested_token=requested_token,
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
                "net_amount": str(request.net_amount),
                "fee_amount": str(request.fee_amount),
                "gross_amount": str(request.gross_amount),
                "currency": request.currency.value,
                "status": request.status.value,
                "requested_network": request.requested_network,
                "requested_token": request.requested_token,
            },
        )
    )

    db.commit()
    db.refresh(request)
    logger.info(
        "Top-up request created | request_id=%s user_id=%s method=%s amount=%s %s",
        request.id,
        request.user_id,
        request.method.value,
        request.amount,
        request.currency.value,
    )
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
    logger.info("Top-up moved to waiting verification | request_id=%s txid_set=true", request.id)
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
    logger.info("Top-up waiting verification updated | request_id=%s", request.id)
    return request


def set_bybit_sender_reference(
    db: Session,
    *,
    request: TopUpRequest,
    sender_uid: str | None = None,
    external_reference: str | None = None,
) -> TopUpRequest:
    if request.method != TopUpMethod.BYBIT_UID:
        raise TopUpRequestTransitionError(
            f"Cannot set Bybit sender/reference for method '{request.method.value}', expected '{TopUpMethod.BYBIT_UID.value}'"
        )
    if request.status != TopUpStatus.PENDING:
        raise TopUpRequestTransitionError(
            f"Cannot set Bybit sender/reference for request in status '{request.status.value}', expected '{TopUpStatus.PENDING.value}'"
        )
    if not sender_uid and not external_reference:
        raise TopUpRequestTransitionError("Cannot set Bybit sender/reference without sender_uid or external_reference")

    ensure_top_up_status_transition(request, TopUpStatus.WAITING_VERIFICATION)
    request.sender_uid = sender_uid
    request.external_reference = external_reference
    request.status = TopUpStatus.WAITING_VERIFICATION

    db.add(
        ActivityLog(
            user_id=request.user_id,
            event_type=LogEventType.TOP_UP_WAITING_VERIFICATION,
            payload={
                "top_up_request_id": request.id,
                "method": request.method.value,
                "status": request.status.value,
                "sender_uid": request.sender_uid,
                "external_reference": request.external_reference,
            },
        )
    )

    db.commit()
    db.refresh(request)
    logger.info(
        "Bybit top-up moved to waiting verification | request_id=%s sender_uid=%s external_reference=%s",
        request.id,
        request.sender_uid,
        request.external_reference,
    )
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
