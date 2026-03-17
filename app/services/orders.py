from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order


def list_user_orders(db: Session, *, user_id: int, limit: int = 5) -> list[Order]:
    return db.scalars(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit)).all()
