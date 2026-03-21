import asyncio
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.bot.handlers import products as products_handlers
from app.db.base import Base
from app.models.category import Category
from app.models.enums import Currency, FulfillmentType, Language, ProductStatus
from app.models.order import Order
from app.models.product_pool import ProductPool
from app.models.reservation import Reservation
from app.models.user import User
from app.models.user_category_price import UserCategoryPrice
from app.services.catalog import get_category_view


class FakeMessage:
    def __init__(self) -> None:
        self.edits: list[dict] = []

    async def edit_text(self, text, reply_markup=None):
        self.edits.append({"text": text, "reply_markup": reply_markup})

    async def answer(self, text, reply_markup=None):
        self.edits.append({"text": text, "reply_markup": reply_markup})


class FakeCallback:
    def __init__(self, *, data: str, message: FakeMessage, telegram_id: int = 777, language_code: str = "en") -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=telegram_id, username="manual", language_code=language_code)
        self.answers: list[dict] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})


def _setup_db_with_seed_prices() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = Session(bind=engine)

    root = Category(name_ru="Игры", name_en="Games")
    steam = Category(name_ru="Steam", name_en="Steam", parent=root)
    db.add_all([root, steam])
    db.flush()

    db.add_all(
        [
            ProductPool(category_id=steam.id, payload="steam-1", status=ProductStatus.AVAILABLE),
            ProductPool(category_id=steam.id, payload="steam-2", status=ProductStatus.AVAILABLE),
        ]
    )

    demo_user = User(
        telegram_id=999000111,
        username="demo_user",
        language=Language.EN,
        currency=Currency.USD,
        balance=Decimal("50.00"),
    )
    db.add(demo_user)
    db.flush()
    db.add(UserCategoryPrice(user_id=demo_user.id, category_id=steam.id, price=Decimal("10.00")))
    db.add(User(telegram_id=777, username="manual", language=Language.EN, currency=Currency.USD))
    db.commit()
    return db


def _setup_db_non_stock_category() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = Session(bind=engine)

    root = Category(name_ru="Услуги", name_en="Services")
    activation = Category(name_ru="Активация", name_en="Activation", parent=root, fulfillment_type=FulfillmentType.ACTIVATION_TASK)
    db.add_all([root, activation])
    db.flush()
    user = User(telegram_id=777, username="manual", language=Language.EN, currency=Currency.USD)
    db.add(user)
    db.flush()
    db.add(UserCategoryPrice(user_id=user.id, category_id=activation.id, price=Decimal("12.00")))
    db.commit()
    return db


def test_catalog_price_fallback_for_manual_user() -> None:
    db = _setup_db_with_seed_prices()
    manual_user = User(telegram_id=12345, username="manual", language=Language.EN, currency=Currency.USD)
    db.add(manual_user)
    db.commit()

    view = get_category_view(db, user_id=manual_user.id, language=Language.EN, category_id=2)
    assert view is not None
    assert view.price == Decimal("10.00")


def test_product_list_has_open_and_reserve_actions(monkeypatch) -> None:
    db = _setup_db_with_seed_prices()
    monkeypatch.setattr(products_handlers, "SessionLocal", lambda: Session(bind=db.get_bind()))

    callback = FakeCallback(data="prod:list:2", message=FakeMessage())
    asyncio.run(products_handlers.on_product_list(callback))

    keyboard = callback.message.edits[-1]["reply_markup"].inline_keyboard
    callback_data = [button.callback_data for row in keyboard for button in row]
    assert "prod:item:2:1" in callback_data
    assert "prod:itembuy:2:1" in callback_data


def test_buy_from_product_flow_creates_reservation_and_order(monkeypatch) -> None:
    db = _setup_db_with_seed_prices()
    monkeypatch.setattr(products_handlers, "SessionLocal", lambda: Session(bind=db.get_bind()))

    callback = FakeCallback(data="prod:itembuy:2:1", message=FakeMessage())
    asyncio.run(products_handlers.on_buy_product(callback))

    reservation = db.scalar(select(Reservation))
    order = db.scalar(select(Order))
    assert reservation is not None
    assert order is not None
    assert "Reservation created" in callback.message.edits[-1]["text"]


def test_buy_from_product_out_of_stock_shows_alert(monkeypatch) -> None:
    db = _setup_db_with_seed_prices()
    product = db.scalar(select(ProductPool).where(ProductPool.id == 1))
    assert product is not None
    product.status = ProductStatus.SOLD
    db.commit()
    monkeypatch.setattr(products_handlers, "SessionLocal", lambda: Session(bind=db.get_bind()))

    callback = FakeCallback(data="prod:itembuy:2:1", message=FakeMessage())
    asyncio.run(products_handlers.on_buy_product(callback))

    assert callback.answers[-1]["show_alert"] is True


def test_non_stock_buy_does_not_crash_without_reservation(monkeypatch) -> None:
    db = _setup_db_non_stock_category()
    monkeypatch.setattr(products_handlers, "SessionLocal", lambda: Session(bind=db.get_bind()))

    callback = FakeCallback(data="prod:buy:2", message=FakeMessage())
    asyncio.run(products_handlers.on_buy(callback))

    order = db.scalar(select(Order))
    assert order is not None
    assert order.reservation_id is None
    assert "Order ID" in callback.message.edits[-1]["text"]
