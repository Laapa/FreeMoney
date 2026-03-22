from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, OrderStatus, PaymentMethod, ProductStatus
from app.models.offer import Offer
from app.models.user import User
from app.models.payment import Payment
from app.services.crypto_pay import CryptoPayInvoice
from app.services.payments import check_order_payment, create_order_payment
from app.services.purchase import reserve_product_for_user
from app.services.admin import add_direct_stock_payload


class FakeCryptoPayClient:
    def __init__(self, *, invoice: CryptoPayInvoice | None = None, invoices: list[CryptoPayInvoice] | None = None):
        self._invoice = invoice
        self._invoices = invoices or []

    def create_invoice(self, *, amount: Decimal, asset: str, expires_in: int) -> CryptoPayInvoice:
        assert self._invoice is not None
        return self._invoice

    def get_invoices(self, *, invoice_ids: list[str] | None = None) -> list[CryptoPayInvoice]:
        return self._invoices


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed_order(db: Session):
    user = User(telegram_id=42, language=Language.EN)
    category = Category(name_ru="Cat", name_en="Cat")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="Offer", name_en="Offer", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add(offer)
    db.flush()
    add_direct_stock_payload(db, offer_id=offer.id, payload="KEY-CP")

    reserve = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("9.99"))
    assert reserve.ok is True
    return reserve.order


def test_create_invoice_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    get_settings.cache_clear()

    db = make_session()
    order = _seed_order(db)

    result = create_order_payment(
        db,
        order=order,
        method=PaymentMethod.CRYPTO_PAY,
        crypto_pay_client=FakeCryptoPayClient(
            invoice=CryptoPayInvoice(
                invoice_id="inv-1",
                status="active",
                amount=Decimal("9.99"),
                pay_url="https://pay.example/1",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
        ),
    )

    assert result.ok is True
    assert order.payment is not None
    assert order.payment.provider_payment_id == "inv-1"


def test_check_invoice_paid_completes_order(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    get_settings.cache_clear()

    db = make_session()
    order = _seed_order(db)
    create_order_payment(
        db,
        order=order,
        method=PaymentMethod.CRYPTO_PAY,
        crypto_pay_client=FakeCryptoPayClient(
            invoice=CryptoPayInvoice(
                invoice_id="inv-1",
                status="active",
                amount=Decimal("9.99"),
                pay_url="https://pay.example/1",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
        ),
    )

    result = check_order_payment(
        db,
        order=order,
        crypto_pay_client=FakeCryptoPayClient(
            invoices=[
                CryptoPayInvoice(
                    invoice_id="inv-1",
                    status="paid",
                    amount=Decimal("9.99"),
                    pay_url="https://pay.example/1",
                    bot_invoice_url=None,
                    expires_at=datetime.utcnow() + timedelta(minutes=10),
                )
            ]
        ),
    )
    db.refresh(order)

    assert result.ok is True
    assert order.status == OrderStatus.DELIVERED
    assert order.product.status == ProductStatus.SOLD


def test_active_invoice_does_not_complete_order(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    get_settings.cache_clear()

    db = make_session()
    order = _seed_order(db)
    create_order_payment(
        db,
        order=order,
        method=PaymentMethod.CRYPTO_PAY,
        crypto_pay_client=FakeCryptoPayClient(
            invoice=CryptoPayInvoice(
                invoice_id="inv-1",
                status="active",
                amount=Decimal("9.99"),
                pay_url="https://pay.example/1",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
        ),
    )

    result = check_order_payment(
        db,
        order=order,
        crypto_pay_client=FakeCryptoPayClient(
            invoices=[
                CryptoPayInvoice(
                    invoice_id="inv-1",
                    status="active",
                    amount=Decimal("9.99"),
                    pay_url="https://pay.example/1",
                    bot_invoice_url=None,
                    expires_at=datetime.utcnow() + timedelta(minutes=10),
                )
            ]
        ),
    )
    db.refresh(order)

    assert result.ok is False
    assert order.status == OrderStatus.PENDING
    assert isinstance(order.payment, Payment)
