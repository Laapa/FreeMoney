from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import Language, ProductStatus
from app.models.product_pool import ProductPool
from app.models.user_category_price import UserCategoryPrice


@dataclass(slots=True)
class CategoryView:
    id: int
    title: str
    parent_id: int | None
    stock_count: int
    price: Decimal | None
    has_children: bool


def _category_title(category: Category, language: Language) -> str:
    return category.name_ru if language == Language.RU else category.name_en


def _category_price(db: Session, *, user_id: int, category_id: int) -> Decimal | None:
    return db.scalar(
        select(UserCategoryPrice.price).where(
            UserCategoryPrice.user_id == user_id,
            UserCategoryPrice.category_id == category_id,
        )
    )


def _category_stock(db: Session, *, category_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ProductPool.id)).where(
                ProductPool.category_id == category_id,
                ProductPool.status == ProductStatus.AVAILABLE,
            )
        )
        or 0
    )


def _has_children(db: Session, *, category_id: int) -> bool:
    return db.scalar(select(func.count(Category.id)).where(Category.parent_id == category_id)) > 0


def list_categories(
    db: Session,
    *,
    user_id: int,
    language: Language,
    parent_id: int | None,
) -> list[CategoryView]:
    categories = db.scalars(
        select(Category)
        .where(Category.parent_id == parent_id)
        .order_by(Category.id)
    ).all()

    result: list[CategoryView] = []
    for category in categories:
        result.append(
            CategoryView(
                id=category.id,
                title=_category_title(category, language),
                parent_id=category.parent_id,
                stock_count=_category_stock(db, category_id=category.id),
                price=_category_price(db, user_id=user_id, category_id=category.id),
                has_children=_has_children(db, category_id=category.id),
            )
        )

    return result


def get_category_view(
    db: Session,
    *,
    user_id: int,
    language: Language,
    category_id: int,
) -> CategoryView | None:
    category = db.get(Category, category_id)
    if category is None:
        return None

    return CategoryView(
        id=category.id,
        title=_category_title(category, language),
        parent_id=category.parent_id,
        stock_count=_category_stock(db, category_id=category.id),
        price=_category_price(db, user_id=user_id, category_id=category.id),
        has_children=_has_children(db, category_id=category.id),
    )


def list_product_cards(
    db: Session,
    *,
    category_id: int,
    price: Decimal | None,
    limit: int = 5,
) -> list[str]:
    products = db.scalars(
        select(ProductPool)
        .where(
            ProductPool.category_id == category_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
        .order_by(ProductPool.id)
        .limit(limit)
    ).all()

    if not products:
        return []

    shown_price = str(price) if price is not None else "-"
    return [f"#{product.id} | {shown_price}" for product in products]
