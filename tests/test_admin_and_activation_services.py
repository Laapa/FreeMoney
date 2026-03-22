from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.core.config import get_settings
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, OrderStatus, PaymentMethod
from app.models.user import User
from app.models.user_category_price import UserCategoryPrice
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

    def check_task(self, task_id: str):
        return type("Resp", (), {"payload": {"data": {"status": "pending"}}, "message": "pending"})


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_admin_whitelist_check() -> None:
    assert admin_service.is_admin_telegram_id(123, {123, 456}) is True
    assert admin_service.is_admin_telegram_id(999, {123, 456}) is False


def test_admin_can_update_price_and_toggle_category() -> None:
    db = make_session()
    category = Category(name_ru="A", name_en="A", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER)
    db.add(category)
    db.commit()

    updated_price = admin_service.update_category_price(db, category_id=category.id, price=Decimal("12.34"))
    toggled = admin_service.update_category_activity(db, category_id=category.id, is_active=False)

    assert updated_price is not None and updated_price.base_price == Decimal("12.34")
    assert toggled is not None and toggled.is_active is False


def test_direct_stock_payload_add_flow_service() -> None:
    db = make_session()
    category = Category(name_ru="Stock", name_en="Stock", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add(category)
    db.commit()

    product = admin_service.add_direct_stock_payload(db, category_id=category.id, payload="SECRET-1")
    count = admin_service.available_payload_count(db, category_id=category.id)

    assert product is not None
    assert count == 1


def test_admin_can_change_manual_supplier_order_status() -> None:
    db = make_session()
    user = User(telegram_id=1122, language=Language.EN)
    category = Category(name_ru="Manual", name_en="Manual", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER)
    db.add_all([user, category])
    db.flush()
    db.add(UserCategoryPrice(user_id=user.id, category_id=category.id, price=Decimal("9.99")))
    db.commit()

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        category_id=category.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
    )
    assert created.ok is True
    created.order.status = OrderStatus.PROCESSING
    db.commit()

    updated = admin_service.update_order_status_for_manual_supplier(
        db,
        order_id=created.order.id,
        new_status=OrderStatus.DELIVERED,
    )
    assert updated is not None
    assert updated.status == OrderStatus.DELIVERED


def test_activation_order_after_paid_dispatches_supplier_task(monkeypatch) -> None:
    monkeypatch.setenv("CRYPTOPAY_API_TOKEN", "token")
    get_settings.cache_clear()
    db = make_session()
    user = User(telegram_id=2002, language=Language.EN)
    category = Category(name_ru="Act", name_en="Act", fulfillment_type=FulfillmentType.ACTIVATION_TASK)
    db.add_all([user, category])
    db.flush()
    db.add(UserCategoryPrice(user_id=user.id, category_id=category.id, price=Decimal("9.99")))
    db.commit()

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        category_id=category.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.ACTIVATION_TASK,
    )
    assert created.ok is True

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
