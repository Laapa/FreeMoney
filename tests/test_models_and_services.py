from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, OrderStatus, PaymentMethod, PaymentStatus, ProductStatus
from app.models.offer import Offer
from app.models.payment import Payment
from app.models.user import User
from app.core.config import get_settings
from app.services.orders import pay_pending_order_from_balance
from app.services.purchase import apply_payment_status, release_expired_reservations, reserve_product_for_user
from app.services.admin import add_direct_stock_payload


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed_direct_offer(db: Session):
    user = User(telegram_id=1, balance=Decimal("100.00"))
    category = Category(name_ru="Cat", name_en="Cat")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="Offer", name_en="Offer", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add(offer)
    db.flush()
    add_direct_stock_payload(db, offer_id=offer.id, payload="item-1")
    db.commit()
    return user, offer


def test_reserve_and_pay_delivers_payload() -> None:
    db = make_session()
    user, offer = _seed_direct_offer(db)

    attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("11.00"))
    assert attempt.ok is True
    assert attempt.order.offer_id == offer.id

    result = pay_pending_order_from_balance(db, user_id=user.id, order_id=attempt.order.id)
    assert result.ok is True
    assert result.order.status == OrderStatus.DELIVERED
    assert result.order.delivered_payload == "item-1"


def test_failed_payment_releases_product() -> None:
    db = make_session()
    user, offer = _seed_direct_offer(db)

    attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("11.00"))
    payment = Payment(order_id=attempt.order.id, amount=Decimal("11.00"), method=PaymentMethod.TEST_STUB, provider="test_stub", status=PaymentStatus.CREATED)
    db.add(payment)
    db.commit()

    apply_payment_status(db, payment, PaymentStatus.FAILED)
    db.refresh(attempt.order)

    assert attempt.order.status == OrderStatus.CANCELED
    assert attempt.order.product.status == ProductStatus.AVAILABLE


def test_release_expired_reservation_returns_stock() -> None:
    db = make_session()
    user, offer = _seed_direct_offer(db)

    attempt = reserve_product_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("10.00"),
        ttl_minutes=1,
        now=datetime.utcnow() - timedelta(minutes=5),
    )
    released = release_expired_reservations(db)
    db.refresh(attempt.order)

    assert released == 1
    assert attempt.order.status == OrderStatus.CANCELED
    assert attempt.order.product.status == ProductStatus.AVAILABLE


def test_reserve_uses_default_ttl_from_settings(monkeypatch) -> None:
    monkeypatch.setenv("PRODUCT_RESERVATION_TTL_MINUTES", "5")
    get_settings.cache_clear()
    db = make_session()
    user, offer = _seed_direct_offer(db)
    now = datetime.utcnow()

    attempt = reserve_product_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("10.00"),
        now=now,
    )

    assert attempt.ok is True
    assert attempt.reservation is not None
    assert attempt.reservation.reserved_until == now + timedelta(minutes=5)
