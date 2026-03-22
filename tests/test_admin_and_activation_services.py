from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, OrderStatus, PaymentMethod
from app.models.offer import Offer
from app.models.user import User
from app.services import admin as admin_service
from app.services.crypto_pay import CryptoPayInvoice
from app.services.payments import check_order_payment, create_order_payment
from app.services.purchase import create_non_stock_order_for_user


class FakeCryptoPayClient:
    def __init__(self, *, invoice: CryptoPayInvoice | None = None, invoices: list[CryptoPayInvoice] | None = None) -> None:
        self.invoice = invoice
        self.invoices = invoices or []

    def create_invoice(self, *, amount: Decimal, asset: str, expires_in: int) -> CryptoPayInvoice:
        assert self.invoice is not None
        return self.invoice

    def get_invoices(self, *, invoice_ids: list[str] | None = None) -> list[CryptoPayInvoice]:
        return self.invoices


class FakeActivationClient:
    def create_task(self, *, code_hash: str, user_token: dict):
        return type("Resp", (), {"payload": {"data": {"task_id": "task-777"}}, "message": "ok"})


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_admin_category_offer_price_and_stock_flow() -> None:
    db = make_session()
    category = admin_service.create_category(db, name_ru="A", name_en="A", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Offer A",
        name_en="Offer A",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("12.34"),
    )
    assert offer is not None

    updated = admin_service.update_offer_price(db, offer_id=offer.id, price=Decimal("10.00"))
    payload = admin_service.add_direct_stock_payload(db, offer_id=offer.id, payload="SECRET-1")

    assert updated is not None and updated.base_price == Decimal("10.00")
    assert payload is not None
    assert admin_service.available_payload_count(db, offer_id=offer.id) == 1


def test_admin_can_change_manual_supplier_order_status() -> None:
    db = make_session()
    user = User(telegram_id=1122, language=Language.EN)
    category = Category(name_ru="Manual", name_en="Manual")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="Manual Offer", name_en="Manual Offer", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER)
    db.add(offer)
    db.commit()

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
    )
    created.order.status = OrderStatus.PROCESSING
    db.commit()

    updated = admin_service.update_order_status_for_manual_supplier(db, order_id=created.order.id, new_status=OrderStatus.DELIVERED)
    assert updated is not None
    assert updated.status == OrderStatus.DELIVERED


def test_activation_order_after_paid_dispatches_supplier_task(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    get_settings.cache_clear()

    db = make_session()
    user = User(telegram_id=2002, language=Language.EN)
    category = Category(name_ru="Act", name_en="Act")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="Act Offer", name_en="Act Offer", fulfillment_type=FulfillmentType.ACTIVATION_TASK)
    db.add(offer)
    db.commit()

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.ACTIVATION_TASK,
    )

    create_order_payment(
        db,
        order=created.order,
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
        order=created.order,
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
        activation_client=FakeActivationClient(),
    )
    db.refresh(created.order)

    assert result.ok is True
    assert created.order.status == OrderStatus.PROCESSING
    assert created.order.external_task_id == "task-777"
