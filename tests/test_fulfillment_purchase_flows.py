from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentStatus, FulfillmentType, Language, OrderStatus, ProductStatus
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_category_price import UserCategoryPrice
from app.services.catalog import get_category_view
from app.services.payments import check_order_payment, create_order_payment
from app.services.purchase import create_non_stock_order_for_user, reserve_product_for_user


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed_user_and_category(db: Session, fulfillment_type: FulfillmentType, telegram_id: int = 4001) -> tuple[User, Category]:
    user = User(telegram_id=telegram_id, language=Language.EN)
    category = Category(name_ru="Cat", name_en="Cat", fulfillment_type=fulfillment_type)
    db.add_all([user, category])
    db.flush()
    db.add(UserCategoryPrice(user_id=user.id, category_id=category.id, price=Decimal("9.99")))
    db.commit()
    return user, category


def test_catalog_availability_for_activation_and_manual_without_stock() -> None:
    db = make_session()
    user, activation = _seed_user_and_category(db, FulfillmentType.ACTIVATION_TASK, telegram_id=4001)
    _, manual = _seed_user_and_category(db, FulfillmentType.MANUAL_SUPPLIER, telegram_id=4002)

    activation_view = get_category_view(db, user_id=user.id, language=Language.EN, category_id=activation.id)
    manual_view = get_category_view(db, user_id=user.id, language=Language.EN, category_id=manual.id)

    assert activation_view is not None and activation_view.is_available is True
    assert manual_view is not None and manual_view.is_available is True


def test_purchase_flow_direct_stock_delivers_after_test_payment_check() -> None:
    db = make_session()
    user, category = _seed_user_and_category(db, FulfillmentType.DIRECT_STOCK)
    db.add(ProductPool(category_id=category.id, payload="KEY-1", status=ProductStatus.AVAILABLE))
    db.commit()

    reserve = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("9.99"))
    assert reserve.ok is True

    created_payment = create_order_payment(db, order=reserve.order)
    assert created_payment.ok is True

    check = check_order_payment(db, order=reserve.order)
    assert check.ok is True

    db.refresh(reserve.order)
    assert reserve.order.status == OrderStatus.DELIVERED
    assert reserve.order.fulfillment_status == FulfillmentStatus.DELIVERED
    assert reserve.order.delivered_payload == "KEY-1"


def test_purchase_flow_activation_task_transitions_to_processing() -> None:
    db = make_session()
    user, category = _seed_user_and_category(db, FulfillmentType.ACTIVATION_TASK)

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        category_id=category.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.ACTIVATION_TASK,
    )
    assert created.ok is True

    pay = create_order_payment(db, order=created.order)
    assert pay.ok is True

    checked = check_order_payment(db, order=created.order)
    assert checked.ok is True

    db.refresh(created.order)
    assert created.order.status == OrderStatus.PROCESSING
    assert created.order.fulfillment_status == FulfillmentStatus.PROCESSING
    assert created.order.external_task_id is not None


def test_purchase_flow_manual_supplier_transitions_to_processing() -> None:
    db = make_session()
    user, category = _seed_user_and_category(db, FulfillmentType.MANUAL_SUPPLIER)

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        category_id=category.id,
        price=Decimal("9.99"),
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
    )
    assert created.ok is True

    create_order_payment(db, order=created.order)
    check_order_payment(db, order=created.order)

    db.refresh(created.order)
    assert created.order.status == OrderStatus.PROCESSING
    assert created.order.fulfillment_status == FulfillmentStatus.PROCESSING
    assert created.order.supplier_note is not None
