from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.services.bybit import BybitClient, BybitClientError, BybitInternalDepositRecord
from app.services.fees import quantize_money
from app.services.top_up_verification import verify_bybit_uid_top_up

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BybitAutoVerifyResult:
    ok: bool
    reason: str
    request: TopUpRequest | None = None
    matched_record: BybitInternalDepositRecord | None = None


SUCCESS_STATUSES = {"success", "completed", "ok", "3", "succeeded"}


def try_auto_verify_bybit_top_up(
    db: Session,
    *,
    request_id: int,
    bybit_client: BybitClient | None = None,
    now: datetime | None = None,
) -> BybitAutoVerifyResult:
    request = db.scalar(select(TopUpRequest).where(TopUpRequest.id == request_id).with_for_update())
    if request is None:
        return BybitAutoVerifyResult(ok=False, reason="request_not_found")
    if request.method != TopUpMethod.BYBIT_UID:
        return BybitAutoVerifyResult(ok=False, reason="invalid_method", request=request)
    if request.credited_at is not None or request.status == TopUpStatus.VERIFIED:
        return BybitAutoVerifyResult(ok=True, reason="already_verified", request=request)
    if request.status != TopUpStatus.WAITING_VERIFICATION:
        return BybitAutoVerifyResult(ok=False, reason=f"invalid_status:{request.status.value}", request=request)

    settings = get_settings()
    current_time = now or datetime.utcnow()
    if not settings.bybit_auto_verify_enabled:
        _mark_attempt(db, request, "auto_verify_disabled", current_time)
        return BybitAutoVerifyResult(ok=False, reason="auto_verify_disabled", request=request)

    if not settings.bybit_api_key or not settings.bybit_api_secret:
        logger.warning("Bybit auto-verify enabled but credentials are missing")
        _mark_attempt(db, request, "credentials_missing", current_time)
        return BybitAutoVerifyResult(ok=False, reason="credentials_missing", request=request)

    if not (settings.bybit_recipient_uid or "").strip():
        _mark_attempt(db, request, "recipient_uid_missing", current_time)
        return BybitAutoVerifyResult(ok=False, reason="recipient_uid_missing", request=request)

    if settings.bybit_require_sender_uid and not request.sender_uid:
        _mark_attempt(db, request, "sender_uid_missing", current_time)
        return BybitAutoVerifyResult(ok=False, reason="sender_uid_missing", request=request)

    client = bybit_client or BybitClient(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
        base_url=settings.bybit_api_base_url,
        recv_window=settings.bybit_recv_window,
        internal_deposit_endpoint=settings.bybit_internal_deposit_endpoint,
    )

    start_time = min(
        request.created_at - timedelta(minutes=5),
        current_time - timedelta(minutes=max(settings.bybit_internal_transfer_lookback_minutes, 1)),
    )
    end_time = current_time

    try:
        records = _fetch_internal_records(
            client,
            coin=settings.bybit_deposit_coin,
            start_time_ms=int(start_time.timestamp() * 1000),
            end_time_ms=int(end_time.timestamp() * 1000),
        )
    except BybitClientError as exc:
        logger.warning("Bybit auto-verify API call failed | request_id=%s error=%s", request.id, str(exc))
        _mark_attempt(db, request, f"api_error:{exc}", current_time)
        return BybitAutoVerifyResult(ok=False, reason="api_error", request=request)

    match = _find_record_match(request=request, records=records, coin=settings.bybit_deposit_coin, require_sender_uid=settings.bybit_require_sender_uid)
    if match is None:
        _mark_attempt(db, request, "not_found", current_time)
        return BybitAutoVerifyResult(ok=False, reason="not_found", request=request)

    verify_result = verify_bybit_uid_top_up(
        db,
        request_id=request.id,
        target_status=TopUpStatus.VERIFIED,
        verification_note=f"Auto-verified via Bybit internal transfer tx={match.tx_id or '-'}",
    )
    if not verify_result.ok or verify_result.request is None:
        return BybitAutoVerifyResult(ok=False, reason=f"verify_failed:{verify_result.error}", request=request)

    verified_request = verify_result.request
    verified_request.verification_source = "auto_bybit"
    verified_request.matched_provider_tx_id = match.tx_id
    verified_request.last_auto_verify_attempt_at = current_time
    verified_request.last_auto_verify_note = "matched"
    db.commit()
    db.refresh(verified_request)
    return BybitAutoVerifyResult(ok=True, reason="verified", request=verified_request, matched_record=match)


def _mark_attempt(db: Session, request: TopUpRequest, note: str, attempted_at: datetime) -> None:
    request.last_auto_verify_attempt_at = attempted_at
    request.last_auto_verify_note = note
    if request.verification_source is None:
        request.verification_source = "pending_auto_bybit"
    db.commit()
    db.refresh(request)


def _fetch_internal_records(
    client: BybitClient,
    *,
    coin: str,
    start_time_ms: int,
    end_time_ms: int,
) -> list[BybitInternalDepositRecord]:
    cursor: str | None = None
    collected: list[BybitInternalDepositRecord] = []
    for _ in range(10):
        page = client.get_internal_deposit_records(
            coin=coin,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            cursor=cursor,
            limit=50,
        )
        collected.extend(page.records)
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    return collected


def _find_record_match(
    *,
    request: TopUpRequest,
    records: list[BybitInternalDepositRecord],
    coin: str,
    require_sender_uid: bool,
) -> BybitInternalDepositRecord | None:
    target_amount = quantize_money(Decimal(request.gross_amount))
    sender_uid = (request.sender_uid or "").strip()
    created_threshold_ms = int((request.created_at - timedelta(minutes=5)).timestamp() * 1000)

    candidates: list[BybitInternalDepositRecord] = []
    for record in records:
        if record.coin.upper() != coin.upper():
            continue
        if _normalize_status(record.status) not in SUCCESS_STATUSES:
            continue
        if quantize_money(record.amount) != target_amount:
            continue
        if record.created_time_ms and record.created_time_ms < created_threshold_ms:
            continue
        if sender_uid:
            if not record.from_member_id or str(record.from_member_id).strip() != sender_uid:
                continue
        elif require_sender_uid:
            continue
        candidates.append(record)

    if not candidates:
        return None

    if not sender_uid and len(candidates) > 1:
        return None

    candidates.sort(key=lambda item: item.created_time_ms, reverse=True)
    return candidates[0]


def _normalize_status(status: str) -> str:
    return (status or "").strip().lower()
