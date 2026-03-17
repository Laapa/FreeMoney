from decimal import Decimal

from sqlalchemy import Numeric, create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.activity_log import ActivityLog
from app.models.enums import Currency, LogEventType, TopUpMethod, TopUpStatus
from app.models.top_up_request import TopUpRequest
from app.models.user import User
from app.services.top_up_requests import create_top_up_request, set_top_up_txid, set_top_up_waiting_verification


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
    request = set_top_up_waiting_verification(db, request=request, reference="bybit_uid_payment")

    assert request.status == TopUpStatus.WAITING_VERIFICATION
    assert request.external_reference == "bybit_uid_payment"
