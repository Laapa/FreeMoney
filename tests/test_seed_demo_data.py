from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.category import Category
from app.models.product_pool import ProductPool
from app.models.user import User
from app.scripts.seed_demo_data import seed_demo_data


def test_seed_demo_data_is_idempotent(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    monkeypatch.setattr("app.scripts.seed_demo_data.SessionLocal", lambda: Session(bind=engine))

    seed_demo_data()
    seed_demo_data()

    with Session(bind=engine) as db:
        categories = db.scalars(select(Category)).all()
        products = db.scalars(select(ProductPool)).all()
        users = db.scalars(select(User).where(User.telegram_id == 999000111)).all()

    assert len(categories) >= 3
    assert len(products) >= 3
    assert len(users) == 1
