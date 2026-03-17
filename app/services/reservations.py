from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.enums import LogEventType, ProductStatus, ReservationStatus
from app.models.product_pool import ProductPool
from app.models.reservation import Reservation


def release_expired_reservations(db: Session, now: datetime | None = None) -> int:
    current_time = now or datetime.utcnow()
    stmt = select(Reservation).where(
        Reservation.status == ReservationStatus.ACTIVE,
        Reservation.reserved_until < current_time,
    )
    expired = db.scalars(stmt).all()

    for reservation in expired:
        reservation.status = ReservationStatus.EXPIRED
        reservation.product.status = ProductStatus.AVAILABLE
        db.add(
            ActivityLog(
                user_id=reservation.user_id,
                reservation_id=reservation.id,
                event_type=LogEventType.RESERVATION_EXPIRED,
                payload={"product_id": reservation.product_id},
            )
        )

    db.commit()
    return len(expired)
