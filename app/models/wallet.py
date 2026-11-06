from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Enum
)
from sqlalchemy.orm import relationship

from app.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)

    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    wallet_number = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    balance = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    pin_hash = Column(String(255), nullable=True)
    failed_pin_attempts = Column(Integer, nullable=False, default=0)
    pin_locked_until = Column(DateTime, nullable=True)

    kyc_level = Column(
        Enum("Minimum", "Full"),
        nullable=False,
        default="Minimum"
    )

    status = Column(
        Enum("Active", "Frozen"),
        nullable=False,
        default="Active"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="wallet"
    )