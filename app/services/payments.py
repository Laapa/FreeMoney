from app.services.purchase import apply_payment_status

__all__ = ["apply_payment_status"]
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.enums import LogEventType, OrderStatus, PaymentStatus, ProductStatus
from app.models.order import Order
from app.models.payment import Payment


def apply_payment_status(db: Session, payment: Payment, new_status: PaymentStatus) -> None:
    payment.status = new_status
    order: Order = payment.order

    if new_status == PaymentStatus.SUCCESS:
        order.status = OrderStatus.PAID
        order.product.status = ProductStatus.SOLD
        db.add(
            ActivityLog(
                user_id=order.user_id,
                order_id=order.id,
                event_type=LogEventType.SALE_COMPLETED,
                payload={"product_id": order.product_id, "payment_id": payment.id},
            )
        )
    elif new_status in {PaymentStatus.FAILED, PaymentStatus.EXPIRED}:
        order.product.status = ProductStatus.AVAILABLE
        db.add(
            ActivityLog(
                user_id=order.user_id,
                order_id=order.id,
                event_type=LogEventType.PAYMENT_FAILED,
                payload={"product_id": order.product_id, "payment_id": payment.id, "status": new_status.value},
            )
        )

    db.commit()
