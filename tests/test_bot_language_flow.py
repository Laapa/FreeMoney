import asyncio
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.bot.handlers import language as language_handlers
from app.bot.handlers import start as start_handlers
from app.bot.i18n import t
from app.db.base import Base
from app.models.enums import Language
from app.models.user import User


class FakeMessage:
    def __init__(self, *, telegram_id: int, username: str = "tester", language_code: str = "en") -> None:
        self.from_user = SimpleNamespace(id=telegram_id, username=username, language_code=language_code)
        self.answers: list[dict] = []

    async def answer(self, text, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


class FakeCallback:
    def __init__(self, *, data: str, message: FakeMessage, telegram_id: int, username: str = "tester") -> None:
        self.data = data
        self.message = message
        self.from_user = SimpleNamespace(id=telegram_id, username=username, language_code="en")
        self.answers: list[dict] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})


def _db_session_factory() -> tuple[object, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    def _session_local() -> Session:
        return Session(bind=engine)

    return _session_local, Session(bind=engine)


def test_new_user_start_shows_language_selection(monkeypatch) -> None:
    session_local, verify_db = _db_session_factory()
    monkeypatch.setattr(start_handlers, "SessionLocal", session_local)

    message = FakeMessage(telegram_id=101)
    asyncio.run(start_handlers.start_handler(message))

    assert message.answers[0]["text"] == t("language_prompt", Language.EN)
    assert verify_db.scalar(select(User).where(User.telegram_id == 101)) is None


def test_language_is_saved_after_selection(monkeypatch) -> None:
    session_local, verify_db = _db_session_factory()
    monkeypatch.setattr(language_handlers, "SessionLocal", session_local)

    message = FakeMessage(telegram_id=102)
    callback = FakeCallback(data="lang:set:ru", message=message, telegram_id=102)
    asyncio.run(language_handlers.on_language_selected(callback))

    user = verify_db.scalar(select(User).where(User.telegram_id == 102))
    assert user is not None
    assert user.language == Language.RU
    assert message.answers[-1]["text"] == t("start", Language.RU)
    menu_rows = message.answers[-1]["reply_markup"].keyboard
    assert menu_rows[0][0].text == t("menu_products", Language.RU)


def test_existing_user_start_uses_saved_language(monkeypatch) -> None:
    session_local, verify_db = _db_session_factory()
    verify_db.add(User(telegram_id=103, username="saved", language=Language.EN))
    verify_db.commit()

    monkeypatch.setattr(start_handlers, "SessionLocal", session_local)

    message = FakeMessage(telegram_id=103, language_code="ru")
    asyncio.run(start_handlers.start_handler(message))

    assert message.answers[-1]["text"] == t("start", Language.EN)
    menu_rows = message.answers[-1]["reply_markup"].keyboard
    assert menu_rows[0][0].text == t("menu_products", Language.EN)


def test_user_can_change_language_later(monkeypatch) -> None:
    session_local, verify_db = _db_session_factory()
    verify_db.add(User(telegram_id=104, username="saved", language=Language.RU))
    verify_db.commit()

    monkeypatch.setattr(language_handlers, "SessionLocal", session_local)

    message = FakeMessage(telegram_id=104)
    open_callback = FakeCallback(data="acc:profile:language", message=message, telegram_id=104)
    asyncio.run(language_handlers.on_profile_language(open_callback))
    assert message.answers[-1]["text"] == t("language_prompt", Language.RU)

    select_callback = FakeCallback(data="lang:set:en", message=message, telegram_id=104)
    asyncio.run(language_handlers.on_language_selected(select_callback))

    updated = verify_db.scalar(select(User).where(User.telegram_id == 104))
    assert updated is not None
    assert updated.language == Language.EN
    assert message.answers[-1]["text"] == t("start", Language.EN)
    menu_rows = message.answers[-1]["reply_markup"].keyboard
    assert menu_rows[1][0].text == t("menu_profile", Language.EN)
