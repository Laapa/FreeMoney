from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.core.config import get_settings
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, OrderStatus, PaymentMethod, ProductStatus
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_category_price import UserCategoryPrice
from app.services.crypto_pay import CryptoPayInvoice
from app.services.payments import check_order_payment, create_order_payment
from app.services.purchase import reserve_product_for_user


class FakeCryptoPayClient:
    def __init__(self, *, invoice: CryptoPayInvoice | None = None, invoices: list[CryptoPayInvoice] | None = None) -> None:
        self.invoice = invoice
        self.invoices = invoices or []

    def create_invoice(self, *, amount: Decimal, asset: str, expires_in: int) -> CryptoPayInvoice:
        assert amount == Decimal("9.99")
        assert asset == "USDT"
        assert expires_in == 1800
        assert self.invoice is not None
        return self.invoice

    def get_invoices(self, *, invoice_ids: list[str] | None = None) -> list[CryptoPayInvoice]:
        assert invoice_ids is not None
        return self.invoices


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed_order(db: Session):
    user = User(telegram_id=5001, language=Language.EN)
    category = Category(name_ru="Cat", name_en="Cat", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add_all([user, category])
    db.flush()
    db.add(UserCategoryPrice(user_id=user.id, category_id=category.id, price=Decimal("9.99")))
    db.add(ProductPool(category_id=category.id, payload="KEY-CP", status=ProductStatus.AVAILABLE))
    db.commit()
    reserve = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("9.99"))
    assert reserve.ok is True
    return reserve.order


def test_create_invoice_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    monkeypatch.setenv("CRYPTOPAY_ASSET", "USDT")
    monkeypatch.setenv("CRYPTOPAY_INVOICE_EXPIRES_IN", "1800")

    get_settings.cache_clear()
    db = make_session()
    order = _seed_order(db)
    invoice = CryptoPayInvoice(
        invoice_id="12345",
        status="active",
        amount=Decimal("9.99"),
        pay_url="https://pay.example/12345",
        bot_invoice_url="https://t.me/CryptoBot?start=invoice-12345",
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    client = FakeCryptoPayClient(invoice=invoice)

    created = create_order_payment(db, order=order, method=PaymentMethod.CRYPTO_PAY, crypto_pay_client=client)
    assert created.ok is True
    assert created.payment is not None
    assert created.payment.provider == "crypto_pay"
    assert created.payment.provider_payment_id == "12345"
    assert created.payment.provider_payment_url == "https://pay.example/12345"


def test_check_invoice_happy_path_and_completes_order(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    get_settings.cache_clear()

    db = make_session()
    order = _seed_order(db)
    create_invoice = CryptoPayInvoice(
        invoice_id="777",
        status="active",
        amount=Decimal("9.99"),
        pay_url="https://pay.example/777",
        bot_invoice_url=None,
        expires_at=datetime.utcnow() + timedelta(minutes=20),
    )
    create_order_payment(db, order=order, method=PaymentMethod.CRYPTO_PAY, crypto_pay_client=FakeCryptoPayClient(invoice=create_invoice))

    paid_invoice = CryptoPayInvoice(
        invoice_id="777",
        status="paid",
        amount=Decimal("9.99"),
        pay_url="https://pay.example/777",
        bot_invoice_url=None,
        expires_at=datetime.utcnow() + timedelta(minutes=20),
    )
    checked = check_order_payment(db, order=order, crypto_pay_client=FakeCryptoPayClient(invoices=[paid_invoice]))
    assert checked.ok is True
    db.refresh(order)
    assert order.status == OrderStatus.DELIVERED


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
                invoice_id="888",
                status="active",
                amount=Decimal("9.99"),
                pay_url="https://pay.example/888",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=20),
            )
        ),
    )

    active_check = check_order_payment(
        db,
        order=order,
        crypto_pay_client=FakeCryptoPayClient(
            invoices=[
                CryptoPayInvoice(
                    invoice_id="888",
                    status="active",
                    amount=Decimal("9.99"),
                    pay_url="https://pay.example/888",
                    bot_invoice_url=None,
                    expires_at=datetime.utcnow() + timedelta(minutes=20),
                )
            ]
        ),
    )
    assert active_check.ok is False
    assert active_check.reason == "payment_pending"
    db.refresh(order)
    assert order.status == OrderStatus.PENDING


def test_duplicate_verification_is_idempotent(monkeypatch) -> None:
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
                invoice_id="999",
                status="active",
                amount=Decimal("9.99"),
                pay_url="https://pay.example/999",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=20),
            )
        ),
    )

    paid_client = FakeCryptoPayClient(
        invoices=[
            CryptoPayInvoice(
                invoice_id="999",
                status="paid",
                amount=Decimal("9.99"),
                pay_url="https://pay.example/999",
                bot_invoice_url=None,
                expires_at=datetime.utcnow() + timedelta(minutes=20),
            )
        ]
    )
    first = check_order_payment(db, order=order, crypto_pay_client=paid_client)
    second = check_order_payment(db, order=order, crypto_pay_client=paid_client)
    assert first.ok is True
    assert second.ok is True
    assert second.reason == "already_paid"
