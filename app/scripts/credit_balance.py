from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User


def credit_user_balance(*, telegram_id: int, amount: Decimal) -> User:
    if amount <= Decimal("0"):
        raise ValueError("Amount must be greater than zero.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            raise ValueError(f"User with telegram_id={telegram_id} was not found.")

        user.balance = user.balance + amount
        db.commit()
        db.refresh(user)
        return user


def main() -> None:
    raw_telegram_id = input("Telegram ID: ").strip()
    raw_amount = input("Credit amount: ").strip()

    try:
        telegram_id = int(raw_telegram_id)
    except ValueError as exc:
        raise ValueError("Telegram ID must be an integer.") from exc

    try:
        amount = Decimal(raw_amount)
    except InvalidOperation as exc:
        raise ValueError("Amount must be a valid decimal number.") from exc

    user = credit_user_balance(telegram_id=telegram_id, amount=amount)
    print(f"Balance credited. User {user.telegram_id} new balance: {user.balance} {user.currency.value}")


if __name__ == "__main__":
    main()
