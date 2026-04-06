from decimal import Decimal
import asyncio

from app.bot.handlers import menu as menu_handler
from app.core.config import get_settings
from app.models.enums import FulfillmentStatus, FulfillmentType, Language, OrderStatus
from app.models.offer import Offer
from app.models.order import Order
from app.models.user import User


class _DummyBot:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append((chat_id, text))


class _DummyCallback:
    def __init__(self, bot: _DummyBot) -> None:
        self.bot = bot


def test_manual_supplier_notification_sent_to_admins(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "1001,1002")
    get_settings.cache_clear()

    bot = _DummyBot()
    callback = _DummyCallback(bot=bot)
    user = User(telegram_id=555, username="buyer", language=Language.RU)
    offer = Offer(category_id=1, name_ru="Ручной", name_en="Manual", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER)
    order = Order(
        user_id=1,
        offer_id=1,
        price=Decimal("12.34"),
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        status=OrderStatus.PROCESSING,
        fulfillment_status=FulfillmentStatus.PROCESSING,
    )

    asyncio.run(menu_handler._notify_admins_manual_order(callback=callback, order=order, offer=offer, user=user))

    assert len(bot.sent) == 2
    assert "требует ручной обработки" in bot.sent[0][1]
    assert "manual_supplier" in bot.sent[0][1]


def test_manual_supplier_notification_failure_does_not_raise(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "1001")
    get_settings.cache_clear()

    bot = _DummyBot(fail=True)
    callback = _DummyCallback(bot=bot)
    user = User(telegram_id=555, username=None, language=Language.RU)
    order = Order(
        user_id=1,
        offer_id=1,
        price=Decimal("12.34"),
        fulfillment_type=FulfillmentType.ACTIVATION_TASK,
        status=OrderStatus.PROCESSING,
        fulfillment_status=FulfillmentStatus.PROCESSING,
    )

    asyncio.run(menu_handler._notify_admins_manual_order(callback=callback, order=order, offer=None, user=user))

    assert bot.sent == []
