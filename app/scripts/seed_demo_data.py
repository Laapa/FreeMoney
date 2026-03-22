from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.enums import Currency, FulfillmentType, Language, ProductStatus
from app.models.offer import Offer
from app.models.product_pool import ProductPool
from app.models.user import User
from app.models.user_offer_price import UserOfferPrice


def _get_or_create_category(db, *, name_ru: str, name_en: str) -> Category:
    existing = db.scalar(select(Category).where(Category.name_en == name_en))
    if existing:
        return existing
    category = Category(name_ru=name_ru, name_en=name_en, is_active=True)
    db.add(category)
    db.flush()
    return category


def _get_or_create_offer(db, *, category_id: int, name_ru: str, name_en: str, fulfillment_type: FulfillmentType) -> Offer:
    existing = db.scalar(select(Offer).where(Offer.category_id == category_id, Offer.name_en == name_en))
    if existing:
        return existing
    offer = Offer(
        category_id=category_id,
        name_ru=name_ru,
        name_en=name_en,
        fulfillment_type=fulfillment_type,
        is_active=True,
        base_price=Decimal("10.00"),
    )
    db.add(offer)
    db.flush()
    return offer


def seed_demo_data() -> None:
    with SessionLocal() as db:
        steam_cat = _get_or_create_category(db, name_ru="Steam Accounts", name_en="Steam Accounts")
        activation_cat = _get_or_create_category(db, name_ru="ChatGPT", name_en="ChatGPT")
        supplier_cat = _get_or_create_category(db, name_ru="Spotify", name_en="Spotify")

        steam_offer = _get_or_create_offer(
            db, category_id=steam_cat.id, name_ru="GTA 5 Steam Account", name_en="GTA 5 Steam Account", fulfillment_type=FulfillmentType.DIRECT_STOCK
        )
        activation_offer = _get_or_create_offer(
            db, category_id=activation_cat.id, name_ru="ChatGPT Plus CDK 1 Month", name_en="ChatGPT Plus CDK 1 Month", fulfillment_type=FulfillmentType.ACTIVATION_TASK
        )
        supplier_offer = _get_or_create_offer(
            db, category_id=supplier_cat.id, name_ru="Spotify Individual 1 Month", name_en="Spotify Individual 1 Month", fulfillment_type=FulfillmentType.MANUAL_SUPPLIER
        )

        for offer_id, payload in [(steam_offer.id, "DEMO-STEAM-KEY-001"), (steam_offer.id, "DEMO-STEAM-KEY-002")]:
            exists = db.scalar(select(ProductPool).where(ProductPool.payload == payload))
            if not exists:
                db.add(ProductPool(offer_id=offer_id, payload=payload, status=ProductStatus.AVAILABLE))

        demo_user = db.scalar(select(User).where(User.telegram_id == 999000111))
        if demo_user is None:
            demo_user = User(telegram_id=999000111, username="demo_user", language=Language.EN, currency=Currency.USD, balance=Decimal("50.00"))
            db.add(demo_user)
            db.flush()

        for offer, price in ((steam_offer, Decimal("10.00")), (activation_offer, Decimal("15.00")), (supplier_offer, Decimal("12.00"))):
            has_price = db.scalar(select(UserOfferPrice).where(UserOfferPrice.user_id == demo_user.id, UserOfferPrice.offer_id == offer.id))
            if not has_price:
                db.add(UserOfferPrice(user_id=demo_user.id, offer_id=offer.id, price=price))

        db.commit()

    print("Demo seed completed (development-only data).")


def main() -> None:
    seed_demo_data()


if __name__ == "__main__":
    main()
