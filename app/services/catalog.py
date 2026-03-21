from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import FulfillmentType, Language, ProductStatus
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
    fulfillment_type: FulfillmentType
    is_available: bool
    availability_label: str


@dataclass(slots=True)
class ProductCard:
    product_id: int


def _category_title(category: Category, language: Language) -> str:
    return category.name_ru if language == Language.RU else category.name_en


def _category_price(db: Session, *, user_id: int, category_id: int) -> Decimal | None:
    personal_price = db.scalar(
        select(UserCategoryPrice.price).where(
            UserCategoryPrice.user_id == user_id,
            UserCategoryPrice.category_id == category_id,
        )
    )
    if personal_price is not None:
        return personal_price

    return db.scalar(
        select(UserCategoryPrice.price)
        .where(UserCategoryPrice.category_id == category_id)
        .order_by(UserCategoryPrice.id.asc())
        .limit(1)
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


def _availability_for_category(category: Category, stock_count: int) -> tuple[bool, str]:
    if category.fulfillment_type == FulfillmentType.DIRECT_STOCK:
        return stock_count > 0, f"in_stock:{stock_count}"
    if category.fulfillment_type == FulfillmentType.ACTIVATION_TASK:
        return True, "activation"
    return True, "supplier"



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
        stock_count = _category_stock(category_id=category.id, children_map=children_map, direct_stock=direct_stock)
        availability, availability_label = _availability_for_category(category, stock_count)
        result.append(
            CategoryView(
                id=category.id,
                title=_category_title(category, language),
                parent_id=category.parent_id,
                stock_count=stock_count,
                price=_category_price(db, user_id=user_id, category_id=category.id),
                has_children=bool(children_map.get(category.id)),
                fulfillment_type=category.fulfillment_type,
                is_available=availability,
                availability_label=availability_label,
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

    availability, availability_label = _availability_for_category(
        category,
        _category_stock(category_id=category.id, children_map=children_map, direct_stock=direct_stock),
    )
    return CategoryView(
        id=category.id,
        title=_category_title(category, language),
        parent_id=category.parent_id,
        stock_count=_category_stock(category_id=category.id, children_map=children_map, direct_stock=direct_stock),
        price=_category_price(db, user_id=user_id, category_id=category.id),
        has_children=bool(children_map.get(category.id)),
        fulfillment_type=category.fulfillment_type,
        is_available=availability,
        availability_label=availability_label,
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


def get_product_card(
    db: Session,
    *,
    category_id: int,
    product_id: int,
) -> ProductCard | None:
    found_product_id = db.scalar(
        select(ProductPool.id).where(
            ProductPool.id == product_id,
            ProductPool.category_id == category_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
    )
    if found_product_id is None:
        return None
    return ProductCard(product_id=found_product_id)
