from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language
from app.models.offer import Offer
from app.models.user import User
from app.models.user_offer_price import UserOfferPrice
from app.services.admin import add_direct_stock_payload
from app.services.catalog import get_offer_view, list_offers
from app.services.purchase import create_non_stock_order_for_user, reserve_product_for_user


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _setup_offer(fulfillment: FulfillmentType = FulfillmentType.DIRECT_STOCK):
    db = make_session()
    user = User(telegram_id=100, language=Language.RU)
    category = Category(name_ru="Steam", name_en="Steam")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="GTA 5", name_en="GTA 5", fulfillment_type=fulfillment, base_price=Decimal("10.00"))
    db.add(offer)
    db.flush()
    db.add(UserOfferPrice(user_id=user.id, offer_id=offer.id, price=Decimal("9.50")))
    if fulfillment == FulfillmentType.DIRECT_STOCK:
        add_direct_stock_payload(db, offer_id=offer.id, payload="steam-1")
    db.commit()
    return db, user, category, offer


def test_offer_list_and_price_resolution() -> None:
    db, user, category, _ = _setup_offer()
    offers = list_offers(db, user_id=user.id, language=Language.RU, category_id=category.id)

    assert len(offers) == 1
    assert offers[0].title == "GTA 5"
    assert offers[0].price == Decimal("9.50")


def test_buy_direct_stock_offer_creates_reservation_and_order() -> None:
    db, user, _, offer = _setup_offer(FulfillmentType.DIRECT_STOCK)
    attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("9.50"))

    assert attempt.ok is True
    assert attempt.order.offer_id == offer.id


def test_buy_non_stock_offer_without_reservation() -> None:
    db, user, _, offer = _setup_offer(FulfillmentType.MANUAL_SUPPLIER)
    created = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("9.50"),
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
    )
    view = get_offer_view(db, user_id=user.id, language=Language.RU, offer_id=offer.id)

    assert created.ok is True
    assert created.order.offer_id == offer.id
    assert view is not None and view.is_available is True
