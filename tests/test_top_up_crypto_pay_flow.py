from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.enums import Currency, Language, TopUpMethod, TopUpStatus
from app.models.user import User
from app.services.crypto_pay import CryptoPayInvoice
from app.services.top_up_payments import check_crypto_pay_top_up, create_crypto_pay_top_up_invoice
from app.services.top_up_requests import create_top_up_request


class FakeCryptoPayClient:
    def __init__(self, *, invoice: CryptoPayInvoice | None = None, invoices: list[CryptoPayInvoice] | None = None):
        self._invoice = invoice
        self._invoices = invoices or []

    def create_invoice(self, *, amount: Decimal, asset: str, expires_in: int) -> CryptoPayInvoice:
        assert self._invoice is not None
        assert amount > Decimal("0")
        return self._invoice

    def get_invoices(self, *, invoice_ids: list[str] | None = None) -> list[CryptoPayInvoice]:
        return self._invoices


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_crypto_pay_top_up_invoice_on_gross_and_credit_only_net(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    from app.core.config import get_settings

    get_settings.cache_clear()

    db = make_session()
    user = User(telegram_id=900, language=Language.EN, currency=Currency.USD, balance=Decimal("0.00"))
    db.add(user)
    db.commit()

    request = create_top_up_request(db, user_id=user.id, method=TopUpMethod.CRYPTO_PAY, amount=Decimal("100.00"), currency=Currency.USD)
    created = create_crypto_pay_top_up_invoice(
        db,
        request_id=request.id,
        crypto_pay_client=FakeCryptoPayClient(
            invoice=CryptoPayInvoice(
                invoice_id="inv-topup-1",
                status="active",
                amount=Decimal("103.00"),
                pay_url="https://pay.example/topup",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
        ),
    )
    assert created.ok is True

    checked = check_crypto_pay_top_up(
        db,
        request_id=request.id,
        crypto_pay_client=FakeCryptoPayClient(
            invoices=[
                CryptoPayInvoice(
                    invoice_id="inv-topup-1",
                    status="paid",
                    amount=Decimal("103.00"),
                    pay_url="https://pay.example/topup",
                    bot_invoice_url=None,
                    expires_at=datetime.utcnow() + timedelta(minutes=10),
                )
            ]
        ),
    )
    db.refresh(user)

    assert checked.ok is True
    assert checked.request is not None
    assert checked.request.status == TopUpStatus.VERIFIED
    assert user.balance == Decimal("100.00")


def test_crypto_pay_top_up_check_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    from app.core.config import get_settings

    get_settings.cache_clear()

    db = make_session()
    user = User(telegram_id=901, language=Language.EN, currency=Currency.USD, balance=Decimal("0.00"))
    db.add(user)
    db.commit()

    request = create_top_up_request(db, user_id=user.id, method=TopUpMethod.CRYPTO_PAY, amount=Decimal("50.00"), currency=Currency.USD)
    create_crypto_pay_top_up_invoice(
        db,
        request_id=request.id,
        crypto_pay_client=FakeCryptoPayClient(
            invoice=CryptoPayInvoice(
                invoice_id="inv-topup-2",
                status="active",
                amount=Decimal("51.50"),
                pay_url="https://pay.example/topup2",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
        ),
    )

    paid_client = FakeCryptoPayClient(
        invoices=[
            CryptoPayInvoice(
                invoice_id="inv-topup-2",
                status="paid",
                amount=Decimal("51.50"),
                pay_url="https://pay.example/topup2",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
        ]
    )
    first = check_crypto_pay_top_up(db, request_id=request.id, crypto_pay_client=paid_client)
    second = check_crypto_pay_top_up(db, request_id=request.id, crypto_pay_client=paid_client)
    db.refresh(user)

    assert first.ok is True
    assert second.ok is True
    assert second.reason == "already_credited"
    assert user.balance == Decimal("50.00")
