from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy import Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserCategoryPrice(Base):
    __tablename__ = "user_category_prices"
    __table_args__ = (UniqueConstraint("user_id", "category_id", name="uq_user_category_price"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    user = relationship("User", back_populates="category_prices")
    category = relationship("Category", back_populates="personal_prices")
