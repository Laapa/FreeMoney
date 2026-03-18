from decimal import Decimal

import pytest
from sqlalchemy import Numeric, create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.activity_log import ActivityLog
from app.models.enums import Currency, LogEventType, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.blockchain.tx_verification import BlockchainVerificationResult, BlockchainVerificationSuccess
from app.services.top_up_requests import create_top_up_request, set_bybit_sender_reference, set_top_up_txid
from app.services.top_up_statuses import TopUpRequestTransitionError
from app.services.top_up_verification import verify_crypto_txid_top_up


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_top_up_amount_column_uses_numeric() -> None:
    assert isinstance(TopUpRequest.__table__.c.amount.type, Numeric)


def test_create_crypto_top_up_starts_with_waiting_txid() -> None:
    db = make_session()
    user = User(telegram_id=777)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("100.50"),
        currency=Currency.USD,
        external_reference="USDT TRC20",
    )

    assert request.status == TopUpStatus.WAITING_TXID
    assert request.txid is None
    assert request.external_reference == "USDT TRC20"


def test_crypto_top_up_txid_transition_to_waiting_verification() -> None:
    db = make_session()
    user = User(telegram_id=778)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("50.00"),
        currency=Currency.USD,
    )
    request = set_top_up_txid(db, request=request, txid="abc123txid")

    logs = db.scalars(select(ActivityLog).where(ActivityLog.user_id == user.id)).all()

    assert request.status == TopUpStatus.WAITING_VERIFICATION
    assert request.txid == "abc123txid"
    assert any(log.event_type == LogEventType.TOP_UP_REQUEST_CREATED for log in logs)
    assert any(log.event_type == LogEventType.TOP_UP_WAITING_VERIFICATION for log in logs)


def test_bybit_top_up_can_be_marked_waiting_verification() -> None:
    db = make_session()
    user = User(telegram_id=779)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("75.00"),
        currency=Currency.USD,
    )
    request = set_bybit_sender_reference(db, request=request, sender_uid="12345678")

    assert request.status == TopUpStatus.WAITING_VERIFICATION
    assert request.sender_uid == "12345678"


def test_bybit_sender_reference_can_store_external_reference() -> None:
    db = make_session()
    user = User(telegram_id=790)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("85.00"),
        currency=Currency.USD,
    )
    request = set_bybit_sender_reference(db, request=request, external_reference="bybit-transfer-123")

    assert request.status == TopUpStatus.WAITING_VERIFICATION
    assert request.sender_uid is None
    assert request.external_reference == "bybit-transfer-123"


def test_set_top_up_txid_rejects_wrong_method() -> None:
    db = make_session()
    user = User(telegram_id=780)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("10.00"),
        currency=Currency.USD,
    )

    with pytest.raises(TopUpRequestTransitionError, match="Cannot set txid for method"):
        set_top_up_txid(db, request=request, txid="abc123txid")


def test_set_top_up_txid_rejects_wrong_status() -> None:
    db = make_session()
    user = User(telegram_id=781)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("10.00"),
        currency=Currency.USD,
    )
    request = set_top_up_txid(db, request=request, txid="abc123txid")

    with pytest.raises(TopUpRequestTransitionError, match="Cannot set txid for request in status"):
        set_top_up_txid(db, request=request, txid="newtxid123")


def test_txid_cannot_be_changed_after_verified() -> None:
    db = make_session()
    user = User(telegram_id=782)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("10.00"),
        currency=Currency.USD,
    )
    request = set_top_up_txid(db, request=request, txid="abc123txid")
    verify_crypto_txid_top_up(
        db,
        request_id=request.id,
        target_status=TopUpStatus.VERIFIED,
        evm_verifier=_AlwaysSuccessVerifier(),
    )
    db.refresh(request)

    with pytest.raises(TopUpRequestTransitionError, match="Cannot set txid for request in status"):
        set_top_up_txid(db, request=request, txid="newtxid123")


class _AlwaysSuccessVerifier:
    def verify_transfer(self, **_kwargs) -> BlockchainVerificationResult:
        return BlockchainVerificationResult(
            ok=True,
            data=BlockchainVerificationSuccess(
                tx_hash="abc123txid",
                network="bsc",
                token="usdt",
                amount=Decimal("10.00"),
                recipient="0xrecipient",
                raw_reference="explorer:https://api.bscscan.com/api",
            ),
        )
