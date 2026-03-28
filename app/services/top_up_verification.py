import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.activity_log import ActivityLog
from app.models.enums import LogEventType, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.blockchain.options import get_supported_crypto_options
from app.services.blockchain.tx_verification import BlockchainVerificationResult, EvmTxVerifier
from app.services.top_up_statuses import TopUpRequestTransitionError, ensure_top_up_status_transition

logger = logging.getLogger(__name__)


class TopUpVerificationError(str, Enum):
    REQUEST_NOT_FOUND = "request_not_found"
    ACCESS_DENIED = "access_denied"
    INVALID_METHOD = "invalid_method"
    TXID_MISSING = "txid_missing"
    INVALID_SOURCE_STATUS = "invalid_source_status"
    INVALID_TARGET_STATUS = "invalid_target_status"
    ALREADY_CREDITED = "already_credited"
    PAYMENT_REFERENCE_MISSING = "payment_reference_missing"
    ON_CHAIN_VERIFICATION_FAILED = "on_chain_verification_failed"


@dataclass(frozen=True)
class TopUpVerificationResult:
    ok: bool
    request: TopUpRequest | None = None
    error: TopUpVerificationError | None = None
    on_chain_result: BlockchainVerificationResult | None = None


_ALLOWED_TARGET_STATUSES = {
    TopUpStatus.VERIFIED,
    TopUpStatus.REJECTED,
    TopUpStatus.EXPIRED,
}


def build_default_evm_verifier() -> EvmTxVerifier:
    settings = get_settings()
    return EvmTxVerifier(
        explorer_urls=settings.blockchain_explorer_base_urls,
        explorer_api_keys=settings.blockchain_explorer_api_keys,
        crypto_options=get_supported_crypto_options(),
        amount_tolerance=_money(settings.blockchain_amount_tolerance),
    )


def verify_crypto_txid_top_up(
    db: Session,
    *,
    request_id: int,
    target_status: TopUpStatus,
    reviewed_by_user_id: int | None = None,
    verification_note: str | None = None,
    evm_verifier: EvmTxVerifier | None = None,
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
    on_chain_result = None
    if target_status == TopUpStatus.VERIFIED:
        on_chain_result = _verify_request_on_chain(request=request, evm_verifier=evm_verifier)
        if not on_chain_result.ok:
            request.reviewed_at = now
            request.verification_note = _build_failed_verification_note(on_chain_result, fallback=verification_note)
            db.commit()
            db.refresh(request)
            logger.warning(
                "Top-up verification failed on-chain | request_id=%s txid=%s reason=%s",
                request.id,
                request.txid,
                on_chain_result.reason.value if on_chain_result.reason else "unknown",
            )
            return TopUpVerificationResult(
                ok=False,
                request=request,
                error=TopUpVerificationError.ON_CHAIN_VERIFICATION_FAILED,
                on_chain_result=on_chain_result,
            )

    request.status = target_status
    request.reviewed_at = now
    request.verification_note = verification_note or (on_chain_result.note if on_chain_result else None)

    event_type = LogEventType.TOP_UP_VERIFIED
    if target_status == TopUpStatus.VERIFIED:
        user = db.scalar(select(User).where(User.id == request.user_id).with_for_update())
        if user is None:
            return TopUpVerificationResult(ok=False, request=request, error=TopUpVerificationError.REQUEST_NOT_FOUND)
        user.balance = _money(user.balance) + _money(request.net_amount)
        request.credited_at = now
        if on_chain_result and on_chain_result.data:
            request.verified_tx_hash = on_chain_result.data.tx_hash
            request.verified_network = on_chain_result.data.network
            request.verified_token = on_chain_result.data.token
            request.verified_amount = on_chain_result.data.amount
            request.verified_recipient = on_chain_result.data.recipient
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
                "net_amount": str(request.net_amount),
                "fee_amount": str(request.fee_amount),
                "gross_amount": str(request.gross_amount),
                "currency": request.currency.value,
                "txid": request.txid,
                "requested_network": request.requested_network,
                "requested_token": request.requested_token,
                "verified_tx_hash": request.verified_tx_hash,
                "verified_network": request.verified_network,
                "verified_token": request.verified_token,
                "verified_amount": str(request.verified_amount) if request.verified_amount is not None else None,
                "verified_recipient": request.verified_recipient,
                "credited_at": request.credited_at.isoformat() if request.credited_at else None,
                "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None,
                "verification_note": request.verification_note,
            },
        )
    )

    db.commit()

    db.refresh(request)
    logger.info(
        "Top-up verification completed | request_id=%s status=%s credited=%s",
        request.id,
        request.status.value,
        bool(request.credited_at),
    )
    return TopUpVerificationResult(ok=True, request=request, on_chain_result=on_chain_result)


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
        user.balance = _money(user.balance) + _money(request.net_amount)
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
                "net_amount": str(request.net_amount),
                "fee_amount": str(request.fee_amount),
                "gross_amount": str(request.gross_amount),
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
    logger.info("Bybit top-up verification completed | request_id=%s status=%s", request.id, request.status.value)
    return TopUpVerificationResult(ok=True, request=request)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _verify_request_on_chain(*, request: TopUpRequest, evm_verifier: EvmTxVerifier | None) -> BlockchainVerificationResult:
    verifier = evm_verifier or build_default_evm_verifier()
    return verifier.verify_transfer(
        tx_hash=request.txid or "",
        expected_network=request.requested_network or "",
        expected_amount=_money(request.gross_amount),
        expected_token_symbol=request.requested_token,
    )


def _build_failed_verification_note(result: BlockchainVerificationResult, fallback: str | None) -> str:
    if result.note:
        return f"On-chain verification failed: {result.note}"
    if result.reason:
        return f"On-chain verification failed: {result.reason.value}"
    return fallback or "On-chain verification failed"
