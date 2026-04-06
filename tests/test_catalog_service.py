from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, ProductStatus
from app.models.offer import Offer
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_offer_price import UserOfferPrice
from app.services.catalog import get_category_view, get_offer_view, list_categories, list_offers, list_product_cards


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_list_categories_and_offers_with_stock_and_prices() -> None:
    db = make_session()
    user = User(telegram_id=1, language=Language.EN)
    category = Category(name_ru="Игры", name_en="Games")
    db.add_all([user, category])
    db.flush()

    offer = Offer(category_id=category.id, name_ru="RUST", name_en="RUST", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add(offer)
    db.flush()
    db.add(UserOfferPrice(user_id=user.id, offer_id=offer.id, price=Decimal("10.00")))
    db.add(ProductPool(offer_id=offer.id, payload="k1", status=ProductStatus.AVAILABLE))
    db.commit()

    categories = list_categories(db, language=Language.EN)
    offers = list_offers(db, user_id=user.id, language=Language.EN, category_id=category.id)

    assert [c.title for c in categories] == ["Games"]
    assert offers[0].title == "RUST"
    assert offers[0].stock_count == 1
    assert offers[0].price == Decimal("10.00")


def test_get_offer_view_and_product_cards() -> None:
    db = make_session()
    user = User(telegram_id=2, language=Language.RU)
    category = Category(name_ru="Софт", name_en="Software")
    db.add_all([user, category])
    db.flush()

    offer = Offer(category_id=category.id, name_ru="ChatGPT Plus", name_en="ChatGPT Plus", fulfillment_type=FulfillmentType.DIRECT_STOCK, base_price=Decimal("5.50"))
    db.add(offer)
    db.flush()
    db.add_all([
        ProductPool(offer_id=offer.id, payload="s1", status=ProductStatus.AVAILABLE),
        ProductPool(offer_id=offer.id, payload="s2", status=ProductStatus.AVAILABLE),
    ])
    db.commit()

    view = get_offer_view(db, user_id=user.id, language=Language.RU, offer_id=offer.id)
    cards = list_product_cards(db, offer_id=offer.id)

    assert view is not None
    assert view.title == "ChatGPT Plus"
    assert view.stock_count == 2
    assert len(cards) == 2


def test_category_view_uses_ru_description_for_ru_user() -> None:
    db = make_session()
    category = Category(
        name_ru="Игры",
        name_en="Games",
        description_ru="Русское описание",
        description_en="English description",
    )
    db.add(category)
    db.commit()

    view = get_category_view(db, language=Language.RU, category_id=category.id)

    assert view is not None
    assert view.description == "Русское описание"


def test_category_view_uses_en_description_for_en_user() -> None:
    db = make_session()
    category = Category(
        name_ru="Игры",
        name_en="Games",
        description_ru="Русское описание",
        description_en="English description",
    )
    db.add(category)
    db.commit()

    view = get_category_view(db, language=Language.EN, category_id=category.id)

    assert view is not None
    assert view.description == "English description"


def test_category_view_description_fallback_to_second_language() -> None:
    db = make_session()
    category = Category(
        name_ru="Игры",
        name_en="Games",
        description_ru="Русское описание",
        description_en="  ",
    )
    db.add(category)
    db.commit()

    view = get_category_view(db, language=Language.EN, category_id=category.id)

    assert view is not None
    assert view.description == "Русское описание"


def test_category_view_without_description_and_offer_list_still_works() -> None:
    db = make_session()
    user = User(telegram_id=77, language=Language.RU)
    category = Category(name_ru="Игры", name_en="Games", description_ru=None, description_en=None)
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="RUST", name_en="RUST", fulfillment_type=FulfillmentType.DIRECT_STOCK)
    db.add(offer)
    db.flush()
    db.add(UserOfferPrice(user_id=user.id, offer_id=offer.id, price=Decimal("7.00")))
    db.add(ProductPool(offer_id=offer.id, payload="key-1", status=ProductStatus.AVAILABLE))
    db.commit()

    view = get_category_view(db, language=Language.RU, category_id=category.id)
    offers = list_offers(db, user_id=user.id, language=Language.RU, category_id=category.id)

    assert view is not None
    assert view.description is None
    assert len(offers) == 1
    assert offers[0].title == "RUST"
