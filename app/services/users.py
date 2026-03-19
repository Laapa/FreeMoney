from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Language
from app.models.user import User


def resolve_language(language_code: str | None) -> Language:
    if not language_code:
        return Language.RU
    return Language.EN if language_code.lower().startswith("en") else Language.RU


def init_or_update_user(
    db: Session,
    *,
    telegram_id: int,
    username: str | None,
    language_code: str | None,
) -> User:
    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    resolved_language = resolve_language(language_code)

    if user is None:
        user = User(telegram_id=telegram_id, username=username, language=resolved_language)
        db.add(user)
    else:
        user.username = username

    db.commit()
    db.refresh(user)
    return user


def get_user_by_telegram_id(db: Session, telegram_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == telegram_id))


def set_user_language(db: Session, *, user: User, language: Language) -> User:
    user.language = language
    db.commit()
    db.refresh(user)
    return user
