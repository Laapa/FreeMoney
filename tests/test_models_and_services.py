from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.activity_log import ActivityLog
from app.models.category import Category
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
