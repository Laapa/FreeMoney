from collections import defaultdict
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


@dataclass(slots=True)
class ProductCard:
    product_id: int


def _category_title(category: Category, language: Language) -> str:
    return category.name_ru if language == Language.RU else category.name_en


def _category_price(db: Session, *, user_id: int, category_id: int) -> Decimal | None:
    return db.scalar(
        select(UserCategoryPrice.price).where(
            UserCategoryPrice.user_id == user_id,
            UserCategoryPrice.category_id == category_id,
        )
    )


def _children_map(db: Session) -> dict[int, list[int]]:
    rows = db.execute(select(Category.id, Category.parent_id)).all()
    mapping: dict[int, list[int]] = defaultdict(list)
    for category_id, parent_id in rows:
        if parent_id is not None:
            mapping[parent_id].append(category_id)
    return mapping


def _collect_descendants(category_id: int, children_map: dict[int, list[int]]) -> set[int]:
    result: set[int] = {category_id}
    stack = [category_id]
    while stack:
        current = stack.pop()
        for child_id in children_map.get(current, []):
            if child_id in result:
                continue
            result.add(child_id)
            stack.append(child_id)
    return result


def _direct_stock_map(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(ProductPool.category_id, func.count(ProductPool.id))
        .where(ProductPool.status == ProductStatus.AVAILABLE)
        .group_by(ProductPool.category_id)
    ).all()
    return {category_id: int(stock_count) for category_id, stock_count in rows}


def _category_stock(*, category_id: int, children_map: dict[int, list[int]], direct_stock: dict[int, int]) -> int:
    return sum(direct_stock.get(descendant_id, 0) for descendant_id in _collect_descendants(category_id, children_map))



def list_categories(
    db: Session,
    *,
    user_id: int,
    language: Language,
    parent_id: int | None,
) -> list[CategoryView]:
    children_map = _children_map(db)
    direct_stock = _direct_stock_map(db)
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
                stock_count=_category_stock(category_id=category.id, children_map=children_map, direct_stock=direct_stock),
                price=_category_price(db, user_id=user_id, category_id=category.id),
                has_children=bool(children_map.get(category.id)),
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
    children_map = _children_map(db)
    direct_stock = _direct_stock_map(db)
    category = db.get(Category, category_id)
    if category is None:
        return None

    return CategoryView(
        id=category.id,
        title=_category_title(category, language),
        parent_id=category.parent_id,
        stock_count=_category_stock(category_id=category.id, children_map=children_map, direct_stock=direct_stock),
        price=_category_price(db, user_id=user_id, category_id=category.id),
        has_children=bool(children_map.get(category.id)),
    )


def get_category_breadcrumbs(db: Session, *, category_id: int, language: Language) -> list[str]:
    chain: list[str] = []
    current_id: int | None = category_id
    while current_id is not None:
        category = db.get(Category, current_id)
        if category is None:
            break
        chain.append(_category_title(category, language))
        current_id = category.parent_id
    chain.reverse()
    return chain


def list_product_cards(
    db: Session,
    *,
    category_id: int,
    limit: int = 5,
) -> list[ProductCard]:
    products = db.scalars(
        select(ProductPool)
        .where(
            ProductPool.category_id == category_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
        .order_by(ProductPool.id)
        .limit(limit)
    ).all()

    return [ProductCard(product_id=product.id) for product in products]
