from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from datetime import datetime, timedelta

from app.models.enums import FulfillmentType, Language, OrderStatus, ProductStatus
from app.models.offer import Offer
from app.models.user import User
from app.services.admin import add_direct_stock_payload
from app.services.orders import get_user_order_stats, pay_pending_order_from_balance
from app.services.payments import create_order_payment
from app.services.purchase import reserve_product_for_user


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed(db: Session):
    user = User(telegram_id=1, language=Language.EN, balance=Decimal("20.00"))
    category = Category(name_ru="Steam", name_en="Steam")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="RUST", name_en="RUST", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add(offer)
    db.flush()
    add_direct_stock_payload(db, offer_id=offer.id, payload="KEY")
    db.commit()
    return user, offer


def test_pay_pending_order_with_balance_delivers_payload() -> None:
    db = make_session()
    user, offer = _seed(db)
    attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("10.00"))

    paid = pay_pending_order_from_balance(db, user_id=user.id, order_id=attempt.order.id)
    assert paid.ok is True
    assert paid.order.status == OrderStatus.DELIVERED
    assert paid.order.delivered_payload == "KEY"


def test_insufficient_balance_keeps_order_pending() -> None:
    db = make_session()
    user, offer = _seed(db)
    user.balance = Decimal("1.00")
    db.commit()
    attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("10.00"))

    paid = pay_pending_order_from_balance(db, user_id=user.id, order_id=attempt.order.id)
    assert paid.ok is False
    assert paid.reason == "insufficient_balance"


def test_profile_stats_include_processing_and_delivered() -> None:
    db = make_session()
    user, offer = _seed(db)
    attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("10.00"))
    attempt.order.status = OrderStatus.PROCESSING
    db.commit()

    stats = get_user_order_stats(db, user_id=user.id)
    assert stats.total_orders == 1
    assert stats.total_spent == Decimal("10.00")


def test_expired_reservation_cannot_be_paid_from_balance() -> None:
    db = make_session()
    user, offer = _seed(db)
    attempt = reserve_product_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("10.00"),
        now=datetime.utcnow() - timedelta(minutes=10),
    )

    paid = pay_pending_order_from_balance(db, user_id=user.id, order_id=attempt.order.id)

    assert paid.ok is False
    assert paid.reason == "order_not_payable"
    db.refresh(attempt.order)
    assert attempt.order.status == OrderStatus.CANCELED
    assert attempt.order.product.status == ProductStatus.AVAILABLE


def test_expired_reservation_cannot_create_external_payment() -> None:
    db = make_session()
    user, offer = _seed(db)
    attempt = reserve_product_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("10.00"),
        now=datetime.utcnow() - timedelta(minutes=10),
    )

    result = create_order_payment(db, order=attempt.order)

    assert result.ok is False
    assert result.reason == "order_not_payable:canceled"
