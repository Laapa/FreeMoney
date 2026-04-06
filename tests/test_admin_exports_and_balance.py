from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.enums import FulfillmentType, Language, OrderStatus, ProductStatus, ReservationStatus
from app.models.offer import Offer
from app.models.order import Order
from app.models.product_pool import ProductPool
from app.models.reservation import Reservation
from app.models.user import User
from app.services import admin as admin_service
from app.services import admin_exports


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_offer_toggle_export_and_safe_delete(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(admin_exports, "_project_root", lambda: tmp_path)
    db = make_session()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Offer",
        name_en="Offer",
        description_ru="desc",
        description_en="desc",
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("10.00"),
    )
    assert offer is not None

    toggled = admin_service.update_offer_activity(db, offer_id=offer.id, is_active=False)
    assert toggled is not None and toggled.is_active is False

    exported_offer, export_path, summary = admin_service.export_offer(db, offer_id=offer.id, reason="test")
    assert exported_offer is not None
    assert export_path is not None
    assert Path(export_path).exists()
    assert summary["exported"] == 0

    user = User(telegram_id=1, language=Language.RU)
    db.add(user)
    db.flush()
    db.add(
        Order(
            user_id=user.id,
            offer_id=offer.id,
            price=Decimal("10.00"),
            fulfillment_type=FulfillmentType.DIRECT_STOCK,
        )
    )
    db.commit()

    ok, details = admin_service.delete_offer(db, offer_id=offer.id)
    assert ok is True
    assert "физически удален" in details


def test_category_export_and_safe_delete(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(admin_exports, "_project_root", lambda: tmp_path)
    db = make_session()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Offer",
        name_en="Offer",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        base_price=Decimal("7.50"),
    )
    assert offer is not None

    exported_category, export_path = admin_service.export_category(db, category_id=category.id, reason="test")
    assert exported_category is not None
    assert export_path is not None and Path(export_path).exists()

    ok, details = admin_service.delete_category(db, category_id=category.id)
    assert ok is True
    assert "Категория физически удалена" in details


def test_direct_stock_delete_and_export_count(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(admin_exports, "_project_root", lambda: tmp_path)
    db = make_session()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Offer",
        name_en="Offer",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("10.00"),
    )
    assert offer is not None
    for idx in range(1, 6):
        db.add(ProductPool(offer_id=offer.id, payload=f"key-{idx}", status=ProductStatus.AVAILABLE))
    db.commit()

    exported_offer, export_path, summary = admin_service.export_offer(db, offer_id=offer.id, reason="test_count", count=2)
    assert exported_offer is not None
    assert export_path is not None and Path(export_path).exists()
    assert summary["available_found"] == 5
    assert summary["exported"] == 2

    ok, details = admin_service.delete_offer(db, offer_id=offer.id, count=2)
    assert ok is True
    assert "удалено остатков: 2" in details
    left = db.query(ProductPool).filter(ProductPool.offer_id == offer.id, ProductPool.status == ProductStatus.AVAILABLE).count()
    assert left == 3

    ok_all, details_all = admin_service.delete_offer(db, offer_id=offer.id, count="all")
    assert ok_all is True
    assert "удалено остатков: 3" in details_all
    left_after_all = db.query(ProductPool).filter(ProductPool.offer_id == offer.id).count()
    assert left_after_all == 0


def test_returned_to_stock_item_is_counted_exported_and_deleted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(admin_exports, "_project_root", lambda: tmp_path)
    db = make_session()
    user = User(telegram_id=7, language=Language.RU)
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Offer",
        name_en="Offer",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("10.00"),
    )
    assert offer is not None
    product = ProductPool(offer_id=offer.id, payload="key-returned", status=ProductStatus.AVAILABLE)
    db.add_all([user, product])
    db.flush()
    reservation = Reservation(
        user_id=user.id,
        product_id=product.id,
        status=ReservationStatus.EXPIRED,
        reserved_until=offer.created_at,
    )
    db.add(reservation)
    db.flush()
    db.add(
        Order(
            user_id=user.id,
            offer_id=offer.id,
            product_id=product.id,
            reservation_id=reservation.id,
            price=Decimal("10.00"),
            status=OrderStatus.CANCELED,
            fulfillment_type=FulfillmentType.DIRECT_STOCK,
        )
    )
    db.commit()

    assert admin_service.available_payload_count(db, offer_id=offer.id) == 1

    _, _, export_summary = admin_service.export_offer(db, offer_id=offer.id, reason="returned", count=1)
    assert export_summary["available_found"] == 1
    assert export_summary["exported"] == 1

    ok, details = admin_service.delete_offer(db, offer_id=offer.id, count=1)
    assert ok is True
    assert "не удалось удалить: 1" in details


def test_returned_to_stock_count_all(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(admin_exports, "_project_root", lambda: tmp_path)
    db = make_session()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Offer",
        name_en="Offer",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("10.00"),
    )
    assert offer is not None
    db.add_all(
        [
            ProductPool(offer_id=offer.id, payload="k1", status=ProductStatus.AVAILABLE),
            ProductPool(offer_id=offer.id, payload="k2", status=ProductStatus.AVAILABLE),
        ]
    )
    db.commit()

    _, _, export_summary = admin_service.export_offer(db, offer_id=offer.id, reason="all", count="all")
    assert export_summary["available_found"] == 2
    assert export_summary["exported"] == 2

    ok, details = admin_service.delete_offer(db, offer_id=offer.id, count="all")
    assert ok is True
    assert "удалено остатков: 2" in details


def test_delete_offer_hard_deletes_when_safe() -> None:
    db = make_session()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Manual",
        name_en="Manual",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        base_price=Decimal("10.00"),
    )
    assert offer is not None

    ok, details = admin_service.delete_offer(db, offer_id=offer.id)
    assert ok is True
    assert "физически удален" in details
    assert db.get(Offer, offer.id) is None


def test_delete_category_hard_deletes_when_safe() -> None:
    db = make_session()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Manual",
        name_en="Manual",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        base_price=Decimal("10.00"),
    )
    assert offer is not None

    ok, details = admin_service.delete_category(db, category_id=category.id)
    assert ok is True
    assert "Категория физически удалена" in details
    assert db.get(Category, category.id) is None


def test_delete_category_fallback_when_hard_delete_fails(monkeypatch) -> None:
    db = make_session()
    user = User(telegram_id=17, language=Language.RU)
    db.add(user)
    db.flush()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Manual",
        name_en="Manual",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        base_price=Decimal("10.00"),
    )
    assert offer is not None
    db.add(
        Order(
            user_id=user.id,
            offer_id=offer.id,
            price=Decimal("10.00"),
            fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        )
    )
    db.commit()

    real_try_delete = admin_service._try_delete_entity

    def _patched_try_delete(db_session, entity):
        if isinstance(entity, Category):
            return False, "blocked_for_test"
        return real_try_delete(db_session, entity)

    monkeypatch.setattr(admin_service, "_try_delete_entity", _patched_try_delete)

    ok, details = admin_service.delete_category(db, category_id=category.id)
    assert ok is True
    assert "выведены из активного меню" in details
    db.refresh(category)
    assert category.is_active is False


def test_delete_offer_fallback_when_hard_delete_fails(monkeypatch) -> None:
    db = make_session()
    category = admin_service.create_category(db, name_ru="Cat", name_en="Cat", description_ru=None, description_en=None)
    offer = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Manual",
        name_en="Manual",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        base_price=Decimal("10.00"),
    )
    assert offer is not None
    monkeypatch.setattr(admin_service, "_try_delete_entity", lambda _db, _entity: (False, "blocked_for_test"))

    ok, details = admin_service.delete_offer(db, offer_id=offer.id)
    assert ok is True
    assert "выведен из активного меню" in details


def test_category_export_contains_mixed_offer_payloads(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(admin_exports, "_project_root", lambda: tmp_path)
    db = make_session()
    category = admin_service.create_category(db, name_ru="Mix", name_en="Mix", description_ru=None, description_en=None)
    direct = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Direct",
        name_en="Direct",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.DIRECT_STOCK,
        base_price=Decimal("10.00"),
    )
    manual = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Manual",
        name_en="Manual",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.MANUAL_SUPPLIER,
        base_price=Decimal("10.00"),
    )
    activation = admin_service.create_offer(
        db,
        category_id=category.id,
        name_ru="Act",
        name_en="Act",
        description_ru=None,
        description_en=None,
        fulfillment_type=FulfillmentType.ACTIVATION_TASK,
        base_price=Decimal("10.00"),
    )
    assert direct and manual and activation
    db.add(ProductPool(offer_id=direct.id, payload="d1", status=ProductStatus.AVAILABLE))
    db.commit()

    _, export_path = admin_service.export_category(db, category_id=category.id, reason="mix")
    assert export_path is not None
    content = Path(export_path).read_text(encoding="utf-8")
    assert "direct_stock_leftovers" in content
    assert "manual_supplier" in content
    assert "activation_task" in content


def test_balance_update_by_telegram_id() -> None:
    db = make_session()
    user = User(telegram_id=123456, language=Language.EN, balance=Decimal("10.00"))
    db.add(user)
    db.commit()

    ok_set, _, old_set, new_set = admin_service.update_user_balance_by_telegram_id(
        db, telegram_id=123456, action="set", amount=Decimal("12.00")
    )
    assert ok_set is True
    assert old_set == Decimal("10.00")
    assert new_set == Decimal("12.00")

    ok_add, _, old_add, new_add = admin_service.update_user_balance_by_telegram_id(
        db, telegram_id=123456, action="add", amount=Decimal("3.00")
    )
    assert ok_add is True
    assert old_add == Decimal("12.00")
    assert new_add == Decimal("15.00")

    ok_sub, _, old_sub, new_sub = admin_service.update_user_balance_by_telegram_id(
        db, telegram_id=123456, action="sub", amount=Decimal("5.00")
    )
    assert ok_sub is True
    assert old_sub == Decimal("15.00")
    assert new_sub == Decimal("10.00")

    ok_fail, msg, _, _ = admin_service.update_user_balance_by_telegram_id(
        db, telegram_id=123456, action="sub", amount=Decimal("20.00")
    )
    assert ok_fail is False
    assert "не может стать отрицательным" in msg
