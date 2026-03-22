from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType
from app.models.offer import Offer
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_offer_price import UserOfferPrice
from app.scripts.seed_demo_data import seed_demo_data


def test_seed_demo_data_is_idempotent(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    monkeypatch.setattr("app.scripts.seed_demo_data.SessionLocal", lambda: Session(bind=engine))

    seed_demo_data()
    seed_demo_data()

    with Session(bind=engine) as db:
        categories = db.scalars(select(Category)).all()
        offers = db.scalars(select(Offer)).all()
        products = db.scalars(select(ProductPool)).all()
        users = db.scalars(select(User).where(User.telegram_id == 999000111)).all()
        prices = db.scalars(select(UserOfferPrice)).all()

    assert len(categories) >= 3
    assert len(offers) >= 3
    assert len(users) == 1
    assert len(prices) >= 3

    steam_offer = next(o for o in offers if o.name_en == "GTA 5 Steam Account")
    activation_offer = next(o for o in offers if o.name_en == "ChatGPT Plus CDK 1 Month")
    supplier_offer = next(o for o in offers if o.name_en == "Spotify Individual 1 Month")

    assert steam_offer.fulfillment_type == FulfillmentType.DIRECT_STOCK
    assert activation_offer.fulfillment_type == FulfillmentType.ACTIVATION_TASK
    assert supplier_offer.fulfillment_type == FulfillmentType.MANUAL_SUPPLIER

    direct_stock_payloads = [product for product in products if product.offer_id == steam_offer.id]
    assert len(direct_stock_payloads) >= 1
