from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint
)

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    __table_args__ = (
        UniqueConstraint(
            "wallet_id",
            name="uq_account_wallet_id"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    account_type = Column(
        Enum(
            "User Wallet",
            "Merchant Wallet",
            "Bank Settlement",
            "Cashback Pool",
            "Fees",
            "Withdrawal Clearing",
            "Hold",
            "Opening Equity"
        ),
        nullable=False
    )

    wallet_id = Column(
        Integer,
        ForeignKey("wallets.id"),
        nullable=True
    )

    balance = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00")
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