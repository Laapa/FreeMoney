from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserOfferPrice(Base):
    __tablename__ = "user_offer_prices"
    __table_args__ = (UniqueConstraint("user_id", "offer_id", name="uq_user_offer_price"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    user = relationship("User", back_populates="offer_prices")
    offer = relationship("Offer", back_populates="personal_prices")
