from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Numeric, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.activity_log import ActivityLog
from app.models.category import Category
from app.models.enums import (
    FulfillmentStatus,
    FulfillmentType,
    LogEventType,
    OrderStatus,
    PaymentStatus,
    ProductStatus,
    ReservationStatus,
)
from app.models.order import Order
from app.models.payment import Payment
from app.models.product_pool import ProductPool
from app.models.user import User
from app.services.purchase import (
    apply_payment_status,
    release_expired_reservations,
    reserve_product_for_user,
)


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def seed_user_category(db: Session) -> tuple[User, Category]:
    user = User(telegram_id=1001)
    category = Category(name_ru="Категория", name_en="Category")
    db.add_all([user, category])
    db.commit()
    return user, category


def test_money_columns_use_numeric() -> None:
    assert isinstance(User.__table__.c.balance.type, Numeric)
    assert isinstance(Order.__table__.c.price.type, Numeric)
    assert isinstance(Payment.__table__.c.amount.type, Numeric)


def test_order_allows_multiple_historical_rows_per_product() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()

    first = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))
    first_payment = Payment(order_id=first.order.id, amount=Decimal("11.00"), status=PaymentStatus.PENDING)
    db.add(first_payment)
    db.commit()
    apply_payment_status(db, first_payment, PaymentStatus.FAILED)

    second = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))

    assert second.ok is True
    assert second.order.product_id == first.order.product_id
    assert first.order.id != second.order.id


def test_reservation_id_remains_unique_for_orders() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()

    attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("10.00"))

    duplicate_order = Order(
        user_id=user.id,
        product_id=attempt.order.product_id,
        reservation_id=attempt.reservation.id,
        price=Decimal("10.00"),
        status=OrderStatus.PENDING,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        fulfillment_status=FulfillmentStatus.PENDING,
    )
    db.add(duplicate_order)

    with pytest.raises(IntegrityError):
        db.commit()


def test_successful_payment_marks_order_delivered_and_stores_payload() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="secret-item", status=ProductStatus.AVAILABLE))
    db.commit()

    attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))
    payment = Payment(order_id=attempt.order.id, amount=Decimal("11.00"), status=PaymentStatus.PENDING)
    db.add(payment)
    db.commit()

    apply_payment_status(db, payment, PaymentStatus.SUCCESS)

    db.refresh(attempt.reservation)
    db.refresh(attempt.order)
    product = db.get(ProductPool, attempt.order.product_id)
    logs = db.scalars(select(ActivityLog).where(ActivityLog.order_id == attempt.order.id)).all()

    assert attempt.reservation.status == ReservationStatus.CONVERTED
    assert attempt.order.status == OrderStatus.DELIVERED
    assert attempt.order.delivered_payload == "secret-item"
    assert attempt.order.delivered_at is not None
    assert product.status == ProductStatus.SOLD
    assert any(log.event_type == LogEventType.DELIVERY_COMPLETED for log in logs)


def test_failed_or_expired_payment_releases_product() -> None:
    for failed_status in (PaymentStatus.FAILED, PaymentStatus.EXPIRED):
        db = make_session()
        user, category = seed_user_category(db)
        db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
        db.commit()

        attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))
        payment = Payment(order_id=attempt.order.id, amount=Decimal("11.00"), status=PaymentStatus.PENDING)
        db.add(payment)
        db.commit()

        apply_payment_status(db, payment, failed_status)

        db.refresh(attempt.reservation)
        db.refresh(attempt.order)
        product = db.get(ProductPool, attempt.order.product_id)

        assert attempt.reservation.status == ReservationStatus.CANCELED
        assert attempt.order.status == OrderStatus.CANCELED
        assert product.status == ProductStatus.AVAILABLE


def test_reservation_retry_uses_next_candidate_after_conflict() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add_all(
        [
            ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE),
            ProductPool(category_id=category.id, payload="item-2", status=ProductStatus.AVAILABLE),
        ]
    )
    db.commit()

    original_execute = db.execute
    calls = {"count": 0}

    def flaky_execute(*args, **kwargs):
        statement = args[0] if args else kwargs.get("statement")
        if hasattr(statement, "table") and getattr(statement.table, "name", None) == "products_pool":
            calls["count"] += 1
            if calls["count"] == 1:
                class FakeResult:
                    rowcount = 0

                return FakeResult()
        return original_execute(*args, **kwargs)

    db.execute = flaky_execute
    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("8.00"))

    assert result.ok is True
    assert result.order.product_id == 2


def test_release_expired_reservations_returns_product_and_cancels_order() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()

    attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("10.00"), ttl_minutes=1)
    count = release_expired_reservations(db, now=datetime.utcnow() + timedelta(minutes=2))

    db.refresh(attempt.reservation)
    db.refresh(attempt.order)
    product = db.get(ProductPool, attempt.order.product_id)

    assert count == 1
    assert attempt.reservation.status == ReservationStatus.EXPIRED
    assert attempt.order.status == OrderStatus.CANCELED
    assert product.status == ProductStatus.AVAILABLE
