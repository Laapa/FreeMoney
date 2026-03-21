from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_category_price import UserCategoryPrice
from app.scripts.seed_demo_data import seed_demo_data


def test_seed_demo_data_is_idempotent(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    monkeypatch.setattr("app.scripts.seed_demo_data.SessionLocal", lambda: Session(bind=engine))

    seed_demo_data()
    seed_demo_data()

    with Session(bind=engine) as db:
        categories = db.scalars(select(Category)).all()
        categories_by_name = {category.name_en: category for category in categories}
        products = db.scalars(select(ProductPool)).all()
        users = db.scalars(select(User).where(User.telegram_id == 999000111)).all()
        prices = db.scalars(select(UserCategoryPrice)).all()

    assert len(categories) >= 4
    assert len(users) == 1
    assert len(prices) >= 3

    steam = categories_by_name["Steam Keys"]
    activation = categories_by_name["Activation Service"]
    supplier = categories_by_name["Supplier Items"]

    assert steam.fulfillment_type == FulfillmentType.DIRECT_STOCK
    assert activation.fulfillment_type == FulfillmentType.ACTIVATION_TASK
    assert supplier.fulfillment_type == FulfillmentType.MANUAL_SUPPLIER

    direct_stock_payloads = [product for product in products if product.category_id == steam.id]
    activation_payloads = [product for product in products if product.category_id == activation.id]
    supplier_payloads = [product for product in products if product.category_id == supplier.id]

    assert len(direct_stock_payloads) >= 1
    assert len(activation_payloads) == 0
    assert len(supplier_payloads) == 0
