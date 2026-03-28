from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import Currency, FulfillmentType, Language, PaymentMethod, TopUpMethod, TopUpStatus
from app.models.offer import Offer
from app.models.user import User
from app.services.fees import calculate_external_fee
from app.services.orders import pay_pending_order_from_balance
from app.services.payments import create_order_payment
from app.services.purchase import reserve_product_for_user
from app.services.top_up_requests import create_top_up_request, set_bybit_sender_reference
from app.services.top_up_verification import verify_bybit_uid_top_up


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_fee_helper_for_100_usd() -> None:
    fee = calculate_external_fee(Decimal("100.00"), fee_percent=Decimal("3.00"))
    assert fee.net_amount == Decimal("100.00")
    assert fee.fee_amount == Decimal("3.00")
    assert fee.gross_amount == Decimal("103.00")


def test_external_order_payment_keeps_order_price_net() -> None:
    db = make_session()
    user = User(telegram_id=500, language=Language.EN, balance=Decimal("0.00"))
    category = Category(name_ru="cat", name_en="cat")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="offer", name_en="offer", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER)
    db.add(offer)
    db.flush()

    attempt = reserve_product_for_user(db, user_id=user.id, offer_id=offer.id, price=Decimal("100.00"), product_id=None)
    if not attempt.ok:
        from app.services.purchase import create_non_stock_order_for_user

        attempt_order = create_non_stock_order_for_user(
            db,
            user_id=user.id,
            offer_id=offer.id,
            price=Decimal("100.00"),
            fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        )
        order = attempt_order.order
    else:
        order = attempt.order

    result = create_order_payment(db, order=order, method=PaymentMethod.TEST_STUB)
    assert result.ok is True
    assert order.price == Decimal("100.00")
    assert result.payment.net_amount == Decimal("100.00")
    assert result.payment.fee_amount == Decimal("3.00")
    assert result.payment.gross_amount == Decimal("103.00")


def test_bybit_topup_credits_only_net_amount() -> None:
    db = make_session()
    user = User(telegram_id=600, language=Language.EN, balance=Decimal("0.00"), currency=Currency.USD)
    db.add(user)
    db.commit()

    request = create_top_up_request(
        db,
        user_id=user.id,
        method=TopUpMethod.BYBIT_UID,
        amount=Decimal("100.00"),
        currency=Currency.USD,
    )
    request = set_bybit_sender_reference(db, request=request, sender_uid="123456")
    result = verify_bybit_uid_top_up(db, request_id=request.id, target_status=TopUpStatus.VERIFIED)

    db.refresh(user)
    assert result.ok is True
    assert request.net_amount == Decimal("100.00")
    assert request.fee_amount == Decimal("3.00")
    assert request.gross_amount == Decimal("103.00")
    assert user.balance == Decimal("100.00")


def test_balance_payment_has_no_additional_fee() -> None:
    db = make_session()
    user = User(telegram_id=700, language=Language.EN, balance=Decimal("100.00"))
    category = Category(name_ru="cat", name_en="cat")
    db.add_all([user, category])
    db.flush()
    offer = Offer(category_id=category.id, name_ru="offer", name_en="offer", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER)
    db.add(offer)
    db.flush()
    from app.services.purchase import create_non_stock_order_for_user

    order_result = create_non_stock_order_for_user(
        db,
        user_id=user.id,
        offer_id=offer.id,
        price=Decimal("100.00"),
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
    )
    paid = pay_pending_order_from_balance(db, user_id=user.id, order_id=order_result.order.id)

    db.refresh(user)
    assert paid.ok is True
    assert paid.payment.net_amount == Decimal("100.00")
    assert paid.payment.fee_amount == Decimal("0.00")
    assert user.balance == Decimal("0.00")
