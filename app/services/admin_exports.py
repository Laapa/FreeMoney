from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.offer import Offer
from app.models.enums import ProductStatus
from app.models.product_pool import ProductPool


@dataclass(slots=True)
class ExportResult:
    file_path: Path
    payload: dict[str, Any]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _row_to_dict(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _serialize(getattr(row, field)) for field in fields}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _write_export(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_offer_snapshot(db: Session, *, offer: Offer, reason: str) -> ExportResult:
    product_rows = db.scalars(
        select(ProductPool)
        .where(ProductPool.offer_id == offer.id)
        .order_by(ProductPool.id.asc())
    ).all()

    payload = {
        "entity_type": "offer",
        "export_reason": reason,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "offer": _row_to_dict(
            offer,
            (
                "id",
                "category_id",
                "name_ru",
                "name_en",
                "description_ru",
                "description_en",
                "fulfillment_type",
                "base_price",
                "is_active",
                "sort_order",
                "created_at",
            ),
        ),
        "direct_stock_payloads": [
            _row_to_dict(product, ("id", "offer_id", "payload", "status", "created_at"))
            for product in product_rows
        ],
    }
    export_path = _project_root() / "exports" / "offers" / f"offer_{offer.id}_{_timestamp()}.json"
    _write_export(export_path, payload)
    return ExportResult(file_path=export_path, payload=payload)


def _direct_stock_leftovers_query(*, offer_id: int):
    return (
        select(ProductPool)
        .where(
            ProductPool.offer_id == offer_id,
            ProductPool.status == ProductStatus.AVAILABLE,
        )
        .order_by(ProductPool.id.asc())
    )


def export_offer_leftovers_snapshot(
    db: Session,
    *,
    offer: Offer,
    reason: str,
    leftovers: list[ProductPool] | None = None,
) -> ExportResult:
    exportable_rows = leftovers
    if exportable_rows is None:
        exportable_rows = db.scalars(_direct_stock_leftovers_query(offer_id=offer.id)).all()

    payload = {
        "entity_type": "offer",
        "export_reason": reason,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "offer": _row_to_dict(
            offer,
            (
                "id",
                "category_id",
                "name_ru",
                "name_en",
                "description_ru",
                "description_en",
                "fulfillment_type",
                "base_price",
                "is_active",
                "sort_order",
                "created_at",
            ),
        ),
        "direct_stock_leftovers": [
            _row_to_dict(product, ("id", "offer_id", "payload", "status", "created_at"))
            for product in exportable_rows
        ],
        "direct_stock_leftovers_count": len(exportable_rows),
    }
    export_path = _project_root() / "exports" / "offers" / f"offer_{offer.id}_{_timestamp()}.json"
    _write_export(export_path, payload)
    return ExportResult(file_path=export_path, payload=payload)


def export_category_snapshot(db: Session, *, category: Category, reason: str) -> ExportResult:
    offers = db.scalars(
        select(Offer)
        .where(Offer.category_id == category.id)
        .order_by(Offer.id.asc())
    ).all()

    payload = {
        "entity_type": "category",
        "export_reason": reason,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "category": _row_to_dict(
            category,
            (
                "id",
                "name_ru",
                "name_en",
                "description_ru",
                "description_en",
                "parent_id",
                "is_active",
                "sort_order",
            ),
        ),
        "offers": [
            _row_to_dict(
                offer,
                (
                    "id",
                    "category_id",
                    "name_ru",
                    "name_en",
                    "description_ru",
                    "description_en",
                    "fulfillment_type",
                    "base_price",
                    "is_active",
                    "sort_order",
                    "created_at",
                ),
            )
            for offer in offers
        ],
    }
    export_path = _project_root() / "exports" / "categories" / f"category_{category.id}_{_timestamp()}.json"
    _write_export(export_path, payload)
    return ExportResult(file_path=export_path, payload=payload)


def export_category_with_offers_snapshot(db: Session, *, category: Category, reason: str) -> ExportResult:
    offers = db.scalars(
        select(Offer)
        .where(Offer.category_id == category.id)
        .order_by(Offer.id.asc())
    ).all()

    offer_rows: list[dict[str, Any]] = []
    for offer in offers:
        offer_payload = _row_to_dict(
            offer,
            (
                "id",
                "category_id",
                "name_ru",
                "name_en",
                "description_ru",
                "description_en",
                "fulfillment_type",
                "base_price",
                "is_active",
                "sort_order",
                "created_at",
            ),
        )
        if offer.fulfillment_type.value == "direct_stock":
            leftovers = db.scalars(_direct_stock_leftovers_query(offer_id=offer.id)).all()
            offer_payload["direct_stock_leftovers"] = [
                _row_to_dict(product, ("id", "offer_id", "payload", "status", "created_at"))
                for product in leftovers
            ]
            offer_payload["direct_stock_leftovers_count"] = len(leftovers)
        offer_rows.append(offer_payload)

    payload = {
        "entity_type": "category",
        "export_reason": reason,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "category": _row_to_dict(
            category,
            (
                "id",
                "name_ru",
                "name_en",
                "description_ru",
                "description_en",
                "parent_id",
                "is_active",
                "sort_order",
            ),
        ),
        "offers": offer_rows,
    }
    export_path = _project_root() / "exports" / "categories" / f"category_{category.id}_{_timestamp()}.json"
    _write_export(export_path, payload)
    return ExportResult(file_path=export_path, payload=payload)


def can_delete_offer(db: Session, *, offer_id: int) -> tuple[bool, str | None]:
    linked_orders = db.scalar(select(Order.id).where(Order.offer_id == offer_id).limit(1))
    if linked_orders is not None:
        return False, "У оффера есть связанные заказы/история, hard delete запрещен"
    return True, None


def can_delete_category(db: Session, *, category_id: int) -> tuple[bool, str | None]:
    offers = db.scalars(select(Offer.id).where(Offer.category_id == category_id)).all()
    if not offers:
        return True, None
    linked_order_offer = db.scalar(select(Order.offer_id).where(Order.offer_id.in_(offers)).limit(1))
    if linked_order_offer is not None:
        return False, "У категории есть офферы со связанными заказами/историей, hard delete запрещен"
    return False, "В категории есть офферы. Сначала удалите офферы или отключите категорию"
