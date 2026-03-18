from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Currency, TopUpMethod, TopUpStatus


class TopUpRequest(Base):
    __tablename__ = "top_up_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    method: Mapped[TopUpMethod] = mapped_column(Enum(TopUpMethod), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False)
    status: Mapped[TopUpStatus] = mapped_column(Enum(TopUpStatus), nullable=False)
    txid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_tx_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_network: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verified_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    verified_recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="top_up_requests")
