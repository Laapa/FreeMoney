from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.bot.handlers import menu as menu_handlers
from app.bot.keyboards.account import order_details_keyboard, orders_keyboard
from app.db.base import Base
from app.models.category import Category
from app.models.enums import Currency, Language, OrderStatus, ProductStatus, ReservationStatus
from app.models.order import Order
from app.models.product_pool import ProductPool
from app.models.user import User
from app.services.orders import get_user_order_stats, pay_pending_order_from_balance
from app.services.purchase import reserve_product_for_user


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def seed_pending_order(db: Session, *, balance: Decimal = Decimal("20.00")) -> tuple[User, Order]:
    user = User(telegram_id=10001, language=Language.EN, currency=Currency.USD, balance=balance)
    category = Category(name_ru="Категория", name_en="Category")
    product = ProductPool(category=category, payload="secret-key", status=ProductStatus.AVAILABLE)
    db.add_all([user, category, product])
    db.commit()

    attempt = reserve_product_for_user(db, user_id=user.id, category_id=category.id, price=Decimal("10.00"), product_id=product.id)
    assert attempt.ok is True
    return user, attempt.order


def test_pay_pending_order_with_balance_delivers_payload() -> None:
    db = make_session()
    user, order = seed_pending_order(db)

    result = pay_pending_order_from_balance(db, user_id=user.id, order_id=order.id)
    db.refresh(user)
    db.refresh(order)

    assert result.ok is True
    assert result.reason == "paid_and_delivered"
    assert user.balance == Decimal("10.00")
    assert order.status == OrderStatus.DELIVERED
    assert order.delivered_payload == "secret-key"
    assert order.delivered_at is not None
    assert order.reservation.status == ReservationStatus.CONVERTED
    assert order.product.status == ProductStatus.SOLD


def test_insufficient_balance_does_not_change_order_or_balance() -> None:
    db = make_session()
    user, order = seed_pending_order(db, balance=Decimal("5.00"))

    result = pay_pending_order_from_balance(db, user_id=user.id, order_id=order.id)
    db.refresh(user)
    db.refresh(order)

    assert result.ok is False
    assert result.reason == "insufficient_balance"
    assert user.balance == Decimal("5.00")
    assert order.status == OrderStatus.PENDING
    assert order.delivered_payload is None


def test_duplicate_payment_attempt_not_double_deducted_or_delivered() -> None:
    db = make_session()
    user, order = seed_pending_order(db, balance=Decimal("30.00"))

    first = pay_pending_order_from_balance(db, user_id=user.id, order_id=order.id)
    second = pay_pending_order_from_balance(db, user_id=user.id, order_id=order.id)
    db.refresh(user)
    db.refresh(order)

    assert first.ok is True
    assert second.ok is False
    assert second.reason == "already_delivered"
    assert user.balance == Decimal("20.00")
    assert order.status == OrderStatus.DELIVERED


def test_payment_flow_commits_once_and_avoids_intermediate_paid_commit() -> None:
    db = make_session()
    user, order = seed_pending_order(db, balance=Decimal("30.00"))
    original_commit = db.commit
    commit_calls = {"count": 0}

    def tracked_commit():
        commit_calls["count"] += 1
        return original_commit()

    db.commit = tracked_commit
    result = pay_pending_order_from_balance(db, user_id=user.id, order_id=order.id)
    db.refresh(order)

    assert result.ok is True
    assert commit_calls["count"] == 1
    assert order.status == OrderStatus.DELIVERED


def test_orders_keyboard_exposes_open_action() -> None:
    db = make_session()
    _, order = seed_pending_order(db)

    keyboard = orders_keyboard(language=Language.EN, page=1, pages=1, orders=[order])
    callback_data = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert f"acc:orders:open:{order.id}" in callback_data


def test_order_payment_screen_keyboard_for_crypto_pay() -> None:
    keyboard = order_details_keyboard(
        language=Language.RU,
        order_id=42,
        can_pay=False,
        show_top_up=True,
        payment_url="https://pay.example/invoice",
        payment_screen=True,
    )
    texts = [button.text for row in keyboard.inline_keyboard for button in row if button.text]
    callback_data = [button.callback_data for row in keyboard.inline_keyboard for button in row if button.callback_data]
    urls = [button.url for row in keyboard.inline_keyboard for button in row if button.url]

    assert "💳 Перейти к оплате" in texts
    assert "🔄 Проверить оплату" in texts
    assert "❌ Отменить оплату" in texts
    assert "https://pay.example/invoice" in urls
    assert "acc:orders:check:42" in callback_data


def test_order_details_render_includes_delivered_payload() -> None:
    db = make_session()
    user, order = seed_pending_order(db)
    pay_pending_order_from_balance(db, user_id=user.id, order_id=order.id)
    delivered = db.scalar(select(Order).where(Order.id == order.id))
    assert delivered is not None

    text = menu_handlers._render_order_details_text(language=Language.EN, order=delivered, currency=user.currency.value)
    assert f"Order #{order.id} details" in text
    assert "Payload" in text
    assert "secret-key" in text


def test_order_details_render_includes_item_title() -> None:
    db = make_session()
    user, order = seed_pending_order(db)
    text = menu_handlers._render_order_details_text(
        language=Language.EN,
        order=order,
        currency=user.currency.value,
        item_title="Steam Keys",
    )
    assert "Item: Steam Keys" in text


def test_profile_stats_include_processing_as_paid() -> None:
    db = make_session()
    user, order = seed_pending_order(db)
    order.status = OrderStatus.PROCESSING
    db.commit()

    stats = get_user_order_stats(db, user_id=user.id)
    assert stats.total_orders == 1
    assert stats.total_spent == Decimal("10.00")
