from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.enums import Currency, TopUpMethod, TopUpStatus
from app.models.user import User
from app.services.top_up_requests import create_top_up_request, set_top_up_txid
from app.services.top_up_verification import TopUpVerificationError, verify_crypto_txid_top_up


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _create_waiting_verification_request(db: Session) -> tuple[User, int]:
    user = User(telegram_id=9001, balance=Decimal("10.00"))
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("25.00"),
        currency=Currency.USD,
    )
    request = set_top_up_txid(db, request=request, txid="abcdef12345")
    return user, request.id


def test_verify_top_up_request_credits_balance_once() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.VERIFIED
    assert result.request.credited_at is not None
    assert user.balance == Decimal("35.00")


def test_rejected_request_does_not_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.REJECTED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.REJECTED
    assert result.request.credited_at is None
    assert user.balance == Decimal("10.00")


def test_expired_request_does_not_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.EXPIRED)

    db.refresh(user)
    assert result.ok is True
    assert result.request is not None
    assert result.request.status == TopUpStatus.EXPIRED
    assert result.request.credited_at is None
    assert user.balance == Decimal("10.00")


def test_invalid_status_transition_is_prevented() -> None:
    db = make_session()
    user = User(telegram_id=9002)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.CRYPTO_TXID,
        amount=Decimal("15.00"),
        currency=Currency.USD,
    )

    result = verify_crypto_txid_top_up(db, request_id=request.id, target_status=TopUpStatus.VERIFIED)

    assert result.ok is False
    assert result.error == TopUpVerificationError.TXID_MISSING


def test_duplicate_verification_does_not_double_credit_balance() -> None:
    db = make_session()
    user, request_id = _create_waiting_verification_request(db)

    first = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED)
    second = verify_crypto_txid_top_up(db, request_id=request_id, target_status=TopUpStatus.VERIFIED)

    db.refresh(user)
    assert first.ok is True
    assert second.ok is False
    assert second.error == TopUpVerificationError.INVALID_SOURCE_STATUS
    assert user.balance == Decimal("35.00")


def test_user_scope_check_blocks_foreign_request() -> None:
    db = make_session()
    owner, request_id = _create_waiting_verification_request(db)

    result = verify_crypto_txid_top_up(
        db,
        request_id=request_id,
        target_status=TopUpStatus.REJECTED,
        reviewed_by_user_id=owner.id + 1,
    )

    assert result.ok is False
    assert result.error == TopUpVerificationError.ACCESS_DENIED
