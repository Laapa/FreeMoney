from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.enums import Currency, Language, TopUpMethod, TopUpStatus
from app.models.user import User
from app.services.bybit import BybitInternalDepositRecord, BybitInternalDepositResult
from app.services.bybit_top_up_verification import try_auto_verify_bybit_top_up
from app.services.top_up_requests import create_top_up_request, set_bybit_sender_reference


class FakeBybitClient:
    def __init__(self, records: list[BybitInternalDepositRecord]):
        self.records = records
        self.called = 0

    def get_internal_deposit_records(self, **_kwargs) -> BybitInternalDepositResult:
        self.called += 1
        return BybitInternalDepositResult(records=self.records, next_cursor=None)


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed_bybit_request(db: Session, *, amount: Decimal = Decimal("100.00")):
    user = User(telegram_id=4444, language=Language.EN, currency=Currency.USD, balance=Decimal("0.00"))
    db.add(user)
    db.commit()

    req = create_top_up_request(db, user_id=user.id, method=TopUpMethod.BYBIT_UID, amount=amount, currency=Currency.USD)
    req = set_bybit_sender_reference(db, request=req, sender_uid="777777")
    return user, req


def test_auto_verify_success_credits_only_net(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_AUTO_VERIFY_ENABLED", "true")
    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    monkeypatch.setenv("BYBIT_RECIPIENT_UID", "9988")
    monkeypatch.setenv("BYBIT_DEPOSIT_COIN", "USDT")
    from app.core.config import get_settings

    get_settings.cache_clear()

    db = make_session()
    user, req = _seed_bybit_request(db)

    record = BybitInternalDepositRecord(
        tx_id="tx-1",
        amount=Decimal("100.00"),
        coin="USDT",
        status="2",
        from_member_id="777777",
        created_time_ms=int((datetime.utcnow() + timedelta(minutes=1)).timestamp() * 1000),
        raw={},
    )

    result = try_auto_verify_bybit_top_up(db, request_id=req.id, bybit_client=FakeBybitClient([record]))
    db.refresh(user)

    assert result.ok is True
    assert result.reason == "verified"
    assert user.balance == Decimal("100.00")


def test_auto_verify_no_match_keeps_waiting(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_AUTO_VERIFY_ENABLED", "true")
    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    monkeypatch.setenv("BYBIT_RECIPIENT_UID", "9988")
    from app.core.config import get_settings

    get_settings.cache_clear()

    db = make_session()
    user, req = _seed_bybit_request(db)

    wrong_amount = BybitInternalDepositRecord(
        tx_id="tx-2",
        amount=Decimal("102.99"),
        coin="USDT",
        status="SUCCESS",
        from_member_id="777777",
        created_time_ms=int(datetime.utcnow().timestamp() * 1000),
        raw={},
    )
    result = try_auto_verify_bybit_top_up(db, request_id=req.id, bybit_client=FakeBybitClient([wrong_amount]))
    db.refresh(user)
    db.refresh(req)

    assert result.ok is False
    assert result.reason == "not_found"
    assert user.balance == Decimal("0.00")


def test_auto_verify_failed_status_3_is_not_accepted(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_AUTO_VERIFY_ENABLED", "true")
    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    monkeypatch.setenv("BYBIT_RECIPIENT_UID", "9988")
    from app.core.config import get_settings

    get_settings.cache_clear()

    db = make_session()
    user, req = _seed_bybit_request(db)

    failed_record = BybitInternalDepositRecord(
        tx_id="tx-failed",
        amount=Decimal("100.00"),
        coin="USDT",
        status="3",
        from_member_id="777777",
        created_time_ms=int(datetime.utcnow().timestamp() * 1000),
        raw={},
    )
    result = try_auto_verify_bybit_top_up(db, request_id=req.id, bybit_client=FakeBybitClient([failed_record]))
    db.refresh(user)

    assert result.ok is False
    assert result.reason == "not_found"
    assert user.balance == Decimal("0.00")


def test_auto_verify_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_AUTO_VERIFY_ENABLED", "true")
    monkeypatch.setenv("BYBIT_API_KEY", "k")
    monkeypatch.setenv("BYBIT_API_SECRET", "s")
    monkeypatch.setenv("BYBIT_RECIPIENT_UID", "9988")
    from app.core.config import get_settings

    get_settings.cache_clear()

    db = make_session()
    user, req = _seed_bybit_request(db)

    record = BybitInternalDepositRecord(
        tx_id="tx-3",
        amount=Decimal("100.00"),
        coin="USDT",
        status="SUCCESS",
        from_member_id="777777",
        created_time_ms=int(datetime.utcnow().timestamp() * 1000),
        raw={},
    )
    client = FakeBybitClient([record])
    first = try_auto_verify_bybit_top_up(db, request_id=req.id, bybit_client=client)
    second = try_auto_verify_bybit_top_up(db, request_id=req.id, bybit_client=client)
    db.refresh(user)

    assert first.ok is True
    assert second.ok is True
    assert second.reason == "already_verified"
    assert user.balance == Decimal("100.00")


def test_auto_verify_disabled_fallback(monkeypatch) -> None:
    monkeypatch.setenv("BYBIT_AUTO_VERIFY_ENABLED", "false")
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    monkeypatch.setenv("BYBIT_RECIPIENT_UID", "9988")
    from app.core.config import get_settings

    get_settings.cache_clear()

    db = make_session()
    user, req = _seed_bybit_request(db)
    result = try_auto_verify_bybit_top_up(db, request_id=req.id, bybit_client=FakeBybitClient([]))
    db.refresh(user)

    assert result.ok is False
    assert result.reason == "auto_verify_disabled"
    assert user.balance == Decimal("0.00")
