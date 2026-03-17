from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import Language, ProductStatus
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_category_price import UserCategoryPrice
from app.services.catalog import get_category_view, list_categories, list_product_cards


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_list_categories_supports_hierarchy_and_stock() -> None:
    db = make_session()
    user = User(telegram_id=1, language=Language.EN)
    root = Category(name_ru="Игры", name_en="Games")
    child = Category(name_ru="Steam", name_en="Steam", parent=root)
    db.add_all([user, root, child])
    db.flush()
    db.add_all(
        [
            UserCategoryPrice(user_id=user.id, category_id=root.id, price=Decimal("10.00")),
            UserCategoryPrice(user_id=user.id, category_id=child.id, price=Decimal("15.00")),
            ProductPool(category_id=root.id, payload="r1", status=ProductStatus.AVAILABLE),
            ProductPool(category_id=child.id, payload="c1", status=ProductStatus.AVAILABLE),
            ProductPool(category_id=child.id, payload="c2", status=ProductStatus.RESERVED),
        ]
    )
    db.commit()

    roots = list_categories(db, user_id=user.id, language=Language.EN, parent_id=None)
    assert len(roots) == 1
    assert roots[0].title == "Games"
    assert roots[0].stock_count == 1
    assert roots[0].has_children is True

    subs = list_categories(db, user_id=user.id, language=Language.RU, parent_id=root.id)
    assert len(subs) == 1
    assert subs[0].title == "Steam"
    assert subs[0].stock_count == 1
    assert subs[0].price == Decimal("15.00")


def test_category_view_and_product_cards() -> None:
    db = make_session()
    user = User(telegram_id=2, language=Language.RU)
    category = Category(name_ru="Софт", name_en="Software")
    db.add_all([user, category])
    db.flush()
    db.add(UserCategoryPrice(user_id=user.id, category_id=category.id, price=Decimal("5.50")))
    db.add_all(
        [
            ProductPool(category_id=category.id, payload="s1", status=ProductStatus.AVAILABLE),
            ProductPool(category_id=category.id, payload="s2", status=ProductStatus.AVAILABLE),
        ]
    )
    db.commit()

    view = get_category_view(db, user_id=user.id, language=Language.RU, category_id=category.id)
    assert view is not None
    assert view.title == "Софт"
    assert view.stock_count == 2

    cards = list_product_cards(db, category_id=category.id, price=view.price)
    assert cards == ["#1 | 5.50", "#2 | 5.50"]
