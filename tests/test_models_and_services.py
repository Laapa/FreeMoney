from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.activity_log import ActivityLog
from app.models.category import Category
from app.models.enums import (
    LogEventType,
    OrderStatus,
    PaymentStatus,
    ProductStatus,
    ReservationStatus,
)
from app.models.payment import Payment
from app.models.product_pool import ProductPool
from app.models.user import User
from app.services.purchase import (
    apply_payment_status,
    release_expired_reservations,
    reserve_product_for_user,
)
from app.models.enums import LogEventType, PaymentStatus, ProductStatus, ReservationStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.product_pool import ProductPool
from app.models.reservation import Reservation
from app.models.user import User
from app.services.payments import apply_payment_status
from app.services.reservations import release_expired_reservations


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


def test_successful_reservation() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()

    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("12.50"))

    assert result.ok is True
    assert result.reservation is not None
    assert result.order is not None
    product = db.get(ProductPool, result.reservation.product_id)
    assert product.status == ProductStatus.RESERVED
    assert result.order.status == OrderStatus.PENDING


def test_no_stock_available() -> None:
    db = make_session()
    user, category = seed_user_category(db)

    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("10.00"))

    assert result.ok is False
    assert result.reason == "no_stock_available"


def test_reservation_expiry_releases_product_and_cancels_order() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()

    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("10.00"), ttl_minutes=1)
    assert result.order is not None

    expired_count = release_expired_reservations(db, now=datetime.utcnow() + timedelta(minutes=2))
    db.refresh(result.reservation)
    db.refresh(result.order)
    product = db.get(ProductPool, result.reservation.product_id)

    assert expired_count == 1
    assert result.reservation.status == ReservationStatus.EXPIRED
    assert result.order.status == OrderStatus.CANCELED
    assert product.status == ProductStatus.AVAILABLE


def test_successful_payment_marks_order_delivered_and_product_sold() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="secret-item", status=ProductStatus.AVAILABLE))
    db.commit()

    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))
def test_successful_payment_marks_entities_consistently() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()
    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))

    payment = Payment(order_id=result.order.id, amount=Decimal("11.00"), status=PaymentStatus.PENDING)
    db.add(payment)
    db.commit()

    apply_payment_status(db, payment, PaymentStatus.SUCCESS)

    db.refresh(result.reservation)
    db.refresh(result.order)
    product = db.get(ProductPool, result.reservation.product_id)
    logs = db.scalars(select(ActivityLog).where(ActivityLog.order_id == result.order.id)).all()

    assert result.reservation.status == ReservationStatus.CONVERTED
    assert result.order.status == OrderStatus.DELIVERED
    assert result.order.delivered_payload == "secret-item"
    assert result.order.delivered_at is not None
    assert product.status == ProductStatus.SOLD
    assert any(log.event_type == LogEventType.DELIVERY_COMPLETED for log in logs)


def test_failed_payment_releases_product_and_allows_reorder() -> None:
    db.refresh(result.reservation)
    db.refresh(result.order)
    product = db.get(ProductPool, result.reservation.product_id)

    assert result.reservation.status == ReservationStatus.CONVERTED
    assert result.order.status == OrderStatus.PAID
    assert product.status == ProductStatus.SOLD


def test_failed_payment_releases_product_and_cancels_flow() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()

    first_attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))
    payment = Payment(order_id=first_attempt.order.id, amount=Decimal("11.00"), status=PaymentStatus.PENDING)
    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))

    payment = Payment(order_id=result.order.id, amount=Decimal("11.00"), status=PaymentStatus.PENDING)
    db.add(payment)
    db.commit()

    apply_payment_status(db, payment, PaymentStatus.FAILED)

    db.refresh(first_attempt.reservation)
    db.refresh(first_attempt.order)
    product = db.get(ProductPool, first_attempt.reservation.product_id)

    assert first_attempt.reservation.status == ReservationStatus.CANCELED
    assert first_attempt.order.status == OrderStatus.CANCELED
    assert product.status == ProductStatus.AVAILABLE

    second_attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("11.00"))
    assert second_attempt.ok is True
    assert second_attempt.order.product_id == first_attempt.order.product_id


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
        result = original_execute(*args, **kwargs)
        statement = args[0] if args else kwargs.get("statement")
        if hasattr(statement, "table") and getattr(statement.table, "name", None) == "products_pool":
            calls["count"] += 1
            if calls["count"] == 1:
                class FakeResult:
                    rowcount = 0

                return FakeResult()
        return result

    db.execute = flaky_execute
    result = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("8.00"))

    assert result.ok is True
    assert result.order is not None
    assert result.order.product_id == 2
    db.refresh(result.reservation)
    db.refresh(result.order)
    product = db.get(ProductPool, result.reservation.product_id)

    logs = db.scalars(select(ActivityLog).where(ActivityLog.order_id == result.order.id)).all()

    assert result.reservation.status == ReservationStatus.CANCELED
    assert result.order.status == OrderStatus.CANCELED
    assert product.status == ProductStatus.AVAILABLE
    assert any(log.event_type == LogEventType.PAYMENT_FAILED for log in logs)


def test_duplicate_reservation_prevention_for_single_item_stock() -> None:
    db = make_session()
    user, category = seed_user_category(db)
    second_user = User(telegram_id=1002)
    db.add(second_user)
    db.add(ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE))
    db.commit()

    first = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("9.99"))
    second = reserve_product_for_user(db, user_id=second_user.id, category_id=category.id, price=Decimal("9.99"))

    assert first.ok is True
    assert second.ok is False
    assert second.reason in {"no_stock_available", "reservation_conflict"}
    reservations_count = len(db.scalars(select(ActivityLog).where(ActivityLog.event_type == LogEventType.RESERVATION_CREATED)).all())
    assert reservations_count == 1
def test_release_expired_reservations_returns_product_to_available() -> None:
    db = make_session()
    user = User(telegram_id=1)
    category = Category(name_ru="Категория", name_en="Category")
    product = ProductPool(category=category, payload="item-1", status=ProductStatus.RESERVED)
    reservation = Reservation(
        user=user,
        product=product,
        status=ReservationStatus.ACTIVE,
        reserved_until=datetime.utcnow() - timedelta(minutes=1),
    )
    db.add_all([user, category, product, reservation])
    db.commit()

    count = release_expired_reservations(db)
    db.refresh(product)
    db.refresh(reservation)

    logs = db.scalars(select(ActivityLog)).all()
    assert count == 1
    assert product.status == ProductStatus.AVAILABLE
    assert reservation.status == ReservationStatus.EXPIRED
    assert logs[0].event_type == LogEventType.RESERVATION_EXPIRED


def test_failed_payment_returns_product_to_available_and_logs() -> None:
    db = make_session()
    user = User(telegram_id=42)
    category = Category(name_ru="Категория", name_en="Category")
    product = ProductPool(category=category, payload="secret", status=ProductStatus.RESERVED)
    order = Order(user=user, product=product, price=10)
    payment = Payment(order=order, amount=10, status=PaymentStatus.PENDING)

    db.add_all([user, category, product, order, payment])
    db.commit()

    apply_payment_status(db, payment, PaymentStatus.FAILED)
    db.refresh(product)

    logs = db.scalars(select(ActivityLog)).all()
    assert product.status == ProductStatus.AVAILABLE
    assert logs[0].event_type == LogEventType.PAYMENT_FAILED
