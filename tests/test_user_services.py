from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import Language, ProductStatus
from app.models.product_pool import ProductPool
from app.models.user import User
from app.services.orders import list_user_orders
from app.services.purchase import reserve_product_for_user
from app.services.users import init_or_update_user, resolve_language


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_resolve_language_defaults_to_ru() -> None:
    assert resolve_language(None) == Language.RU
    assert resolve_language("ru") == Language.RU
    assert resolve_language("en") == Language.EN
    assert resolve_language("en-US") == Language.EN


def test_init_or_update_user_creates_and_updates() -> None:
    db = make_session()

    created = init_or_update_user(db, telegram_id=111, username="first", language_code="en")
    assert created.telegram_id == 111
    assert created.language == Language.EN

    updated = init_or_update_user(db, telegram_id=111, username="second", language_code="ru")
    assert updated.id == created.id
    assert updated.username == "second"
    assert updated.language == Language.RU


def test_list_user_orders_sorted_desc() -> None:
    db = make_session()
    user = User(telegram_id=1)
    category = Category(name_ru="Категория", name_en="Category")
    db.add_all([user, category])
    db.flush()
    db.add_all(
        [
            ProductPool(category_id=category.id, payload="item-1", status=ProductStatus.AVAILABLE),
            ProductPool(category_id=category.id, payload="item-2", status=ProductStatus.AVAILABLE),
        ]
    )
    db.commit()

    first = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("1.00"))
    second = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("2.00"))

    orders = list_user_orders(db, user_id=user.id, limit=10)
    assert [o.id for o in orders] == [second.order.id, first.order.id]
