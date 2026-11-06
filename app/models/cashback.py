from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Enum
)

from app.database import Base


class Cashback(Base):
    __tablename__ = "cashbacks"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    transaction_id = Column(
        Integer,
        ForeignKey("transactions.id"),
        unique=True,
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00")
    )

    status = Column(
        Enum(
            "Pending",
            "Credited",
            "Cancelled"
        ),
        nullable=False,
        default="Pending"
    )

    eligible_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(hours=24)
    )

    credited_at = Column(
        DateTime,
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )