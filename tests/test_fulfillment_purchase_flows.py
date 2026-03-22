from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, OrderStatus, PaymentMethod, PaymentStatus
from app.models.offer import Offer
from app.models.payment import Payment
from app.models.user import User
from app.services.catalog import get_offer_view
from app.services.purchase import apply_payment_status, create_non_stock_order_for_user


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed_user_and_offer(db: Session, fulfillment_type: FulfillmentType, telegram_id: int = 4001):
    user = User(telegram_id=telegram_id, language=Language.EN)
    category = Category(name_ru="Cat", name_en="Cat")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="Offer", name_en="Offer", fulfillment_type=fulfillment_type, base_price=Decimal("9.99"))
    db.add(offer)
    db.commit()
    return user, offer


def test_catalog_availability_for_activation_and_manual_without_stock() -> None:
    db = make_session()
    user, activation = _seed_user_and_offer(db, FulfillmentType.ACTIVATION_TASK)
    _, manual = _seed_user_and_offer(db, FulfillmentType.MANUAL_SUPPLIER, telegram_id=4002)

    activation_view = get_offer_view(db, user_id=user.id, language=Language.EN, offer_id=activation.id)
    manual_view = get_offer_view(db, user_id=user.id, language=Language.EN, offer_id=manual.id)

    assert activation_view and activation_view.is_available is True
    assert manual_view and manual_view.is_available is True


def test_purchase_flow_activation_task_transitions_to_processing() -> None:
    db = make_session()
    user, offer = _seed_user_and_offer(db, FulfillmentType.ACTIVATION_TASK)

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.ACTIVATION_TASK,
    )
    payment = Payment(order_id=created.order.id, amount=Decimal("9.99"), method=PaymentMethod.TEST_STUB, provider="test_stub", status=PaymentStatus.CREATED)
    db.add(payment)
    db.commit()

    apply_payment_status(db, payment, PaymentStatus.SUCCESS)
    db.refresh(created.order)

    assert created.order.status == OrderStatus.PROCESSING
    assert created.order.offer_id == offer.id


def test_purchase_flow_manual_supplier_transitions_to_processing() -> None:
    db = make_session()
    user, offer = _seed_user_and_offer(db, FulfillmentType.MANUAL_SUPPLIER)

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
    )
    payment = Payment(order_id=created.order.id, amount=Decimal("9.99"), method=PaymentMethod.TEST_STUB, provider="test_stub", status=PaymentStatus.CREATED)
    db.add(payment)
    db.commit()

    apply_payment_status(db, payment, PaymentStatus.SUCCESS)
    db.refresh(created.order)

    assert created.order.status == OrderStatus.PROCESSING
    assert created.order.offer_id == offer.id
