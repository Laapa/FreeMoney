from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import FulfillmentType, Language, ProductStatus
from app.models.offer import Offer
from app.models.product_pool import ProductPool
from app.models.user_offer_price import UserOfferPrice


@dataclass(slots=True)
class CategoryView:
    id: int
    title: str


@dataclass(slots=True)
class OfferView:
    id: int
    category_id: int
    title: str
    description: str | None
    stock_count: int
    price: Decimal | None
    fulfillment_type: FulfillmentType
    is_available: bool
    availability_label: str


@dataclass(slots=True)
class ProductCard:
    product_id: int


def _category_title(category: Category, language: Language) -> str:
    return category.name_ru if language == Language.RU else category.name_en


def _offer_title(offer: Offer, language: Language) -> str:
    return offer.name_ru if language == Language.RU else offer.name_en


def _offer_description(offer: Offer, language: Language) -> str | None:
    return offer.description_ru if language == Language.RU else offer.description_en


def _offer_price(db: Session, *, user_id: int, offer: Offer) -> Decimal | None:
    personal_price = db.scalar(
        select(UserOfferPrice.price).where(
            UserOfferPrice.user_id == user_id,
            UserOfferPrice.offer_id == offer.id,
        )
    )
    if personal_price is not None:
        return personal_price
    if offer.base_price is not None:
        return offer.base_price
    return db.scalar(select(UserOfferPrice.price).where(UserOfferPrice.offer_id == offer.id).order_by(UserOfferPrice.id.asc()).limit(1))


def _direct_stock_map(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(ProductPool.offer_id, func.count(ProductPool.id))
        .where(ProductPool.status == ProductStatus.AVAILABLE)
        .group_by(ProductPool.offer_id)
    ).all()
    return {offer_id: int(stock_count) for offer_id, stock_count in rows}


def _availability_for_offer(offer: Offer, stock_count: int) -> tuple[bool, str]:
    if offer.fulfillment_type == FulfillmentType.DIRECT_STOCK:
        return stock_count > 0, f"in_stock:{stock_count}"
    if offer.fulfillment_type == FulfillmentType.ACTIVATION_TASK:
        return True, "activation"
    return True, "supplier"


def list_categories(db: Session, *, language: Language) -> list[CategoryView]:
    categories = db.scalars(
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.sort_order.asc(), Category.id.asc())
    ).all()
    return [CategoryView(id=category.id, title=_category_title(category, language)) for category in categories]


def get_category_view(db: Session, *, language: Language, category_id: int) -> CategoryView | None:
    category = db.get(Category, category_id)
    if category is None or not category.is_active:
        return None
    return CategoryView(id=category.id, title=_category_title(category, language))


def list_offers(db: Session, *, user_id: int, language: Language, category_id: int) -> list[OfferView]:
    direct_stock = _direct_stock_map(db)
    offers = db.scalars(
        select(Offer)
        .where(Offer.category_id == category_id, Offer.is_active.is_(True))
        .order_by(Offer.sort_order.asc(), Offer.id.asc())
    ).all()

    result: list[OfferView] = []
    for offer in offers:
        stock_count = direct_stock.get(offer.id, 0)
        availability, label = _availability_for_offer(offer, stock_count)
        result.append(
            OfferView(
                id=offer.id,
                category_id=offer.category_id,
                title=_offer_title(offer, language),
                description=_offer_description(offer, language),
                stock_count=stock_count,
                price=_offer_price(db, user_id=user_id, offer=offer),
                fulfillment_type=offer.fulfillment_type,
                is_available=availability,
                availability_label=label,
            )
        )
    return result


def get_offer_view(db: Session, *, user_id: int, language: Language, offer_id: int) -> OfferView | None:
    offer = db.get(Offer, offer_id)
    if offer is None or not offer.is_active:
        return None
    stock_count = _direct_stock_map(db).get(offer.id, 0)
    availability, label = _availability_for_offer(offer, stock_count)
    return OfferView(
        id=offer.id,
        category_id=offer.category_id,
        title=_offer_title(offer, language),
        description=_offer_description(offer, language),
        stock_count=stock_count,
        price=_offer_price(db, user_id=user_id, offer=offer),
        fulfillment_type=offer.fulfillment_type,
        is_available=availability,
        availability_label=label,
    )


def get_category_breadcrumbs(db: Session, *, category_id: int, language: Language) -> list[str]:
    category = db.get(Category, category_id)
    if category is None:
        return []
    return [_category_title(category, language)]


def list_product_cards(db: Session, *, offer_id: int, limit: int = 5) -> list[ProductCard]:
    products = db.scalars(
        select(ProductPool)
        .where(
            ProductPool.offer_id == offer_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
        .order_by(ProductPool.id)
        .limit(limit)
    ).all()
    return [ProductCard(product_id=product.id) for product in products]


def get_product_card(db: Session, *, offer_id: int, product_id: int) -> ProductCard | None:
    found_product_id = db.scalar(
        select(ProductPool.id).where(
            ProductPool.id == product_id,
            ProductPool.offer_id == offer_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
    )
    if found_product_id is None:
        return None
    return ProductCard(product_id=found_product_id)
