from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.enums import Currency, Language, ProductStatus
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_category_price import UserCategoryPrice


def _get_or_create_category(db, *, name_ru: str, name_en: str, parent_id: int | None = None) -> Category:
    existing = db.scalar(
        select(Category).where(Category.name_en == name_en, Category.parent_id == parent_id)
    )
    if existing:
        return existing
    category = Category(name_ru=name_ru, name_en=name_en, parent_id=parent_id)
    db.add(category)
    db.flush()
    return category


def seed_demo_data() -> None:
    with SessionLocal() as db:
        root_games = _get_or_create_category(db, name_ru="Игры", name_en="Games")
        steam = _get_or_create_category(db, name_ru="Steam", name_en="Steam", parent_id=root_games.id)
        xbox = _get_or_create_category(db, name_ru="Xbox", name_en="Xbox", parent_id=root_games.id)

        products = [
            (steam.id, "DEMO-STEAM-KEY-001"),
            (steam.id, "DEMO-STEAM-KEY-002"),
            (xbox.id, "DEMO-XBOX-KEY-001"),
        ]
        for category_id, payload in products:
            exists = db.scalar(select(ProductPool).where(ProductPool.payload == payload))
            if exists:
                continue
            db.add(ProductPool(category_id=category_id, payload=payload, status=ProductStatus.AVAILABLE))

        demo_user = db.scalar(select(User).where(User.telegram_id == 999000111))
        if demo_user is None:
            demo_user = User(
                telegram_id=999000111,
                username="demo_user",
                language=Language.EN,
                currency=Currency.USD,
                balance=Decimal("50.00"),
            )
            db.add(demo_user)
            db.flush()

        for category, price in ((steam, Decimal("10.00")), (xbox, Decimal("15.00"))):
            has_price = db.scalar(
                select(UserCategoryPrice).where(
                    UserCategoryPrice.user_id == demo_user.id,
                    UserCategoryPrice.category_id == category.id,
                )
            )
            if not has_price:
                db.add(UserCategoryPrice(user_id=demo_user.id, category_id=category.id, price=price))

        db.commit()

    print("Demo seed completed (development-only data).")


def main() -> None:
    seed_demo_data()


if __name__ == "__main__":
    main()
