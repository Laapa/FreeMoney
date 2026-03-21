from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FulfillmentStatus, FulfillmentType, OrderStatus


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("reservation_id", name="uq_order_reservation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products_pool.id"), nullable=True)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"), nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(Enum(FulfillmentType), nullable=False)
    fulfillment_status: Mapped[FulfillmentStatus] = mapped_column(
        Enum(FulfillmentStatus), default=FulfillmentStatus.PENDING, nullable=False
    )
    external_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="orders")
    product = relationship("ProductPool", back_populates="orders")
    reservation = relationship("Reservation", back_populates="order")
    payment = relationship("Payment", back_populates="order", uselist=False)
