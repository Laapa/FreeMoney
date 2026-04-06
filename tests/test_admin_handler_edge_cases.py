import asyncio
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.bot.handlers import admin as admin_handler
from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language
from app.models.user import User
from app.services import admin as admin_service


class DummyFromUser:
    def __init__(self, user_id: int):
        self.id = user_id


class DummyMessage:
    def __init__(self, text: str, user_id: int = 1):
        self.text = text
        self.from_user = DummyFromUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append(text)


class _SessionLocalCtx:
    def __init__(self, session: Session):
        self.session = session

    def __call__(self):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_batch_offer_import_survives_invalid_category_id(monkeypatch) -> None:
    db = _make_session()
    category = admin_service.create_category(db, name_ru="A", name_en="A", description_ru=None, description_en=None)

    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    message = DummyMessage(
        "\n".join(
            [
                "OFFER|oops|Bad|Bad|manual_supplier|10.00|desc|desc",
                f"OFFER|{category.id}|Good|Good|manual_supplier|11.00|desc|desc",
            ]
        )
    )

    asyncio.run(admin_handler.admin_offer_input(message))

    assert message.answers
    assert "Создано офферов: 1" in message.answers[-1]
    assert "Строка 1: category_id должен быть числом" in message.answers[-1]


def test_invalid_ids_in_admin_commands_return_human_message(monkeypatch) -> None:
    db = _make_session()
    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    cat_msg = DummyMessage("TOGGLE_CAT|abc|off")
    asyncio.run(admin_handler.admin_categories_input(cat_msg))
    assert "category_id должен быть числом" in cat_msg.answers[-1]

    offer_msg = DummyMessage("TOGGLE_OFFER|bad|on")
    asyncio.run(admin_handler.admin_offer_input(offer_msg))
    assert "offer_id должен быть числом" in offer_msg.answers[-1]


def test_category_multiline_toggle_export_delete(monkeypatch) -> None:
    db = _make_session()
    cat1 = admin_service.create_category(db, name_ru="C1", name_en="C1", description_ru=None, description_en=None)
    cat2 = admin_service.create_category(db, name_ru="C2", name_en="C2", description_ru=None, description_en=None)

    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    toggle_msg = DummyMessage(f"TOGGLE_CAT|{cat1.id}|off\nTOGGLE_CAT|{cat2.id}|off")
    asyncio.run(admin_handler.admin_categories_input(toggle_msg))
    assert "TOGGLE_CAT выполнено: 2" in toggle_msg.answers[-1]

    export_msg = DummyMessage(f"EXPORT_CAT|{cat1.id}\nEXPORT_CAT|bad")
    asyncio.run(admin_handler.admin_categories_input(export_msg))
    assert "Строка 1: экспорт" in export_msg.answers[-1]
    assert "Строка 2: category_id должен быть числом" in export_msg.answers[-1]

    delete_msg = DummyMessage(f"DELETE_CAT|{cat1.id}\nDELETE_CAT|bad")
    asyncio.run(admin_handler.admin_categories_input(delete_msg))
    assert "Строка 1:" in delete_msg.answers[-1]
    assert "Строка 2: category_id должен быть числом" in delete_msg.answers[-1]


def test_price_bad_offer_id_returns_validation_error(monkeypatch) -> None:
    db = _make_session()
    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    message = DummyMessage("PRICE|bad|10")
    asyncio.run(admin_handler.admin_offer_input(message))
    assert message.answers[-1] == "offer_id должен быть числом"


def test_payload_bad_offer_id_returns_validation_error(monkeypatch) -> None:
    db = _make_session()
    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    message = DummyMessage("PAYLOAD|oops|text")
    asyncio.run(admin_handler.admin_payload_add_input(message))
    assert "offer_id должен быть числом" in message.answers[-1]


def test_payload_batch_add_with_partial_errors(monkeypatch) -> None:
    db = _make_session()
    category = admin_service.create_category(db, name_ru="A", name_en="A", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Stock",
        name_en="Stock",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("10"),
    )
    assert offer is not None
    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    message = DummyMessage(f"PAYLOAD|{offer.id}|k1\nPAYLOAD|bad|k2\nPAYLOAD|{offer.id}|k3")
    asyncio.run(admin_handler.admin_payload_add_input(message))
    assert "Добавлено payload: 2" in message.answers[-1]
    assert "Строка 2: offer_id должен быть числом" in message.answers[-1]


def test_offer_multiline_toggle_export_delete(monkeypatch) -> None:
    db = _make_session()
    category = admin_service.create_category(db, name_ru="A", name_en="A", description_ru=None, description_en=None)
    offer1 = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="O1",
        name_en="O1",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        base_price=Decimal("1"),
    )
    offer2 = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="O2",
        name_en="O2",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("1"),
    )
    assert offer1 and offer2
    admin_service.add_direct_stock_payload(db, offer_id=offer2.id, payload="x")

    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    toggle_msg = DummyMessage(f"TOGGLE_OFFER|{offer1.id}|off\nTOGGLE_OFFER|{offer2.id}|off")
    asyncio.run(admin_handler.admin_offer_input(toggle_msg))
    assert "TOGGLE_OFFER выполнено: 2" in toggle_msg.answers[-1]

    export_msg = DummyMessage(f"EXPORT_OFFER|{offer2.id}|all\nEXPORT_OFFER|bad|10")
    asyncio.run(admin_handler.admin_offer_input(export_msg))
    assert "Строка 1: экспорт" in export_msg.answers[-1]
    assert "Строка 2: offer_id должен быть числом" in export_msg.answers[-1]

    delete_msg = DummyMessage(f"DELETE_OFFER|{offer2.id}|1\nDELETE_OFFER|bad|all")
    asyncio.run(admin_handler.admin_offer_input(delete_msg))
    assert "Строка 1:" in delete_msg.answers[-1]
    assert "Строка 2: offer_id должен быть числом" in delete_msg.answers[-1]


def test_manual_and_act_bad_order_id_return_validation_error(monkeypatch) -> None:
    db = _make_session()
    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    manual_message = DummyMessage("MANUAL|bad|delivered")
    asyncio.run(admin_handler.admin_order_update_global(manual_message))
    assert manual_message.answers[-1] == "order_id должен быть числом"

    act_message = DummyMessage("ACT|oops")
    asyncio.run(admin_handler.admin_activation_refresh_global(act_message))
    assert act_message.answers[-1] == "order_id должен быть числом"


def test_topup_verify_bad_request_id_returns_validation_error(monkeypatch) -> None:
    db = _make_session()
    monkeypatch.setattr(admin_handler, "_is_admin", lambda _telegram_id: True)
    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    message = DummyMessage("TOPUP_VERIFY|bad|verified")
    asyncio.run(admin_handler.admin_topup_verify(message))
    assert message.answers[-1] == "request_id должен быть числом"


def test_admin_exit_language_resolves_from_user(monkeypatch) -> None:
    db = _make_session()
    user = User(telegram_id=777, language=Language.EN, balance=Decimal("0.00"))
    db.add(user)
    db.commit()

    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    assert admin_handler._exit_language_for_user(777) == Language.EN
    assert admin_handler._exit_language_for_user(999999) == Language.RU
