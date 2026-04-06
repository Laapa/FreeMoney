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
    assert cat_msg.answers[-1] == "category_id должен быть числом"

    offer_msg = DummyMessage("TOGGLE_OFFER|bad|on")
    asyncio.run(admin_handler.admin_offer_input(offer_msg))
    assert offer_msg.answers[-1] == "offer_id должен быть числом"


def test_admin_exit_language_resolves_from_user(monkeypatch) -> None:
    db = _make_session()
    user = User(telegram_id=777, language=Language.EN, balance=Decimal("0.00"))
    db.add(user)
    db.commit()

    monkeypatch.setattr(admin_handler, "SessionLocal", _SessionLocalCtx(db))

    assert admin_handler._exit_language_for_user(777) == Language.EN
    assert admin_handler._exit_language_for_user(999999) == Language.RU
