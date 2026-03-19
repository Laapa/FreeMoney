from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.enums import Currency, Language
from app.models.user import User
from app.scripts import credit_balance as credit_balance_script


def test_credit_user_balance_updates_existing_user(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(bind=engine) as db:
        db.add(User(telegram_id=123456, language=Language.EN, currency=Currency.USD, balance=Decimal("5.00")))
        db.commit()

    monkeypatch.setattr(credit_balance_script, "SessionLocal", lambda: Session(bind=engine))
    user = credit_balance_script.credit_user_balance(telegram_id=123456, amount=Decimal("7.50"))

    assert user.balance == Decimal("12.50")


def test_credit_user_balance_requires_existing_user(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(credit_balance_script, "SessionLocal", lambda: Session(bind=engine))

    with pytest.raises(ValueError):
        credit_balance_script.credit_user_balance(telegram_id=999999, amount=Decimal("1.00"))
