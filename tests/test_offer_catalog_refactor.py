from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, OrderStatus, ProductStatus
from app.models.offer import Offer
from app.models.user import User
from app.models.user_offer_price import UserOfferPrice
from app.services import admin as admin_service
from app.services.catalog import get_offer_view, list_categories, list_offers
from app.services.orders import pay_pending_order_from_balance
from app.services.purchase import create_non_stock_order_for_user, reserve_product_for_user


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_category_and_offer_list_flow() -> None:
    db = make_session()
    user = User(telegram_id=1, language=Language.RU)
    category = Category(name_ru="Steam", name_en="Steam")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="GTA 5", name_en="GTA 5", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add(offer)
    db.flush()
    db.add(UserOfferPrice(user_id=user.id, offer_id=offer.id, price=Decimal("10.00")))
    db.commit()

    categories = list_categories(db, language=Language.RU)
    offers = list_offers(db, user_id=user.id, language=Language.RU, category_id=category.id)
    assert categories[0].title == "Steam"
    assert offers[0].title == "GTA 5"
    assert offers[0].price == Decimal("10.00")


def test_purchase_by_offer_and_order_stores_offer_id() -> None:
    db = make_session()
    user = User(telegram_id=2, language=Language.EN, balance=Decimal("50.00"))
    category = Category(name_ru="Steam", name_en="Steam")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="RUST", name_en="RUST", fulfillment_type=FulfillmentType.DIRECT_STOCK, base_price=Decimal("8.00"))
    db.add(offer)
    db.flush()
    admin_service.add_direct_stock_payload(db, offer_id=offer.id, payload="KEY-1")

    reserve = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("8.00"))
    assert reserve.ok is True
    assert reserve.order.offer_id == offer.id

    paid = pay_pending_order_from_balance(db, user_id=user.id, order_id=reserve.order.id)
    assert paid.ok is True
    assert paid.order.status == OrderStatus.DELIVERED


def test_personal_price_overrides_base_price() -> None:
    db = make_session()
    user = User(telegram_id=3, language=Language.EN)
    category = Category(name_ru="ChatGPT", name_en="ChatGPT")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="Plus", name_en="Plus", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER, base_price=Decimal("20.00"))
    db.add(offer)
    db.flush()
    db.add(UserOfferPrice(user_id=user.id, offer_id=offer.id, price=Decimal("15.00")))
    db.commit()

    view = get_offer_view(db, user_id=user.id, language=Language.EN, offer_id=offer.id)
    assert view is not None
    assert view.price == Decimal("15.00")


def test_activation_and_manual_are_available_without_stock() -> None:
    db = make_session()
    user = User(telegram_id=4, language=Language.EN)
    category = Category(name_ru="Services", name_en="Services")
    db.add_all([user, category])
    db.flush()
    activation = Offer(category_id=category.id, name_ru="Activation", name_en="Activation", fulfillment_type=FulfillmentType.ACTIVATION_TASK, base_price=Decimal("5.00"))
    manual = Offer(category_id=category.id, name_ru="Manual", name_en="Manual", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER, base_price=Decimal("6.00"))
    db.add_all([activation, manual])
    db.commit()

    av = get_offer_view(db, user_id=user.id, language=Language.EN, offer_id=activation.id)
    mv = get_offer_view(db, user_id=user.id, language=Language.EN, offer_id=manual.id)
    assert av and av.is_available is True
    assert mv and mv.is_available is True


def test_admin_can_create_category_offer_update_price_and_add_payload() -> None:
    db = make_session()
    category = admin_service.create_category(db, name_ru="Spotify", name_en="Spotify", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Individual 1M",
        name_en="Individual 1M",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("9.00"),
    )
    assert offer is not None
    updated = admin_service.update_offer_price(db, offer_id=offer.id, price=Decimal("7.50"))
    assert updated and updated.base_price == Decimal("7.50")
    payload = admin_service.add_direct_stock_payload(db, offer_id=offer.id, payload="ACC")
    assert payload is not None and payload.status == ProductStatus.AVAILABLE


def test_non_stock_offer_purchase_flow() -> None:
    db = make_session()
    user = User(telegram_id=5)
    category = Category(name_ru="ChatGPT", name_en="ChatGPT")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="Pro", name_en="Pro", fulfillment_type=FulfillmentType.ACTIVATION_TASK, base_price=Decimal("11.00"))
    db.add(offer)
    db.commit()

    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("11.00"),
        fulfillment_type=FulfillmentType.ACTIVATION_TASK,
    )
    assert created.ok is True
    assert created.order.offer_id == offer.id
