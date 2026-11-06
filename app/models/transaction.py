from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Enum,
    Boolean,
    Text,
    UniqueConstraint
)

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        UniqueConstraint(
            "initiated_by",
            "idempotency_key",
            name="uq_transaction_user_idempotency"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    transaction_ref = Column(
        String(40),
        unique=True,
        nullable=False,
        index=True
    )

    type = Column(
        Enum(
            "Add Money",
            "P2P Transfer",
            "Merchant Payment",
            "Merchant Refund",
            "Cashback",
            "Cashback Pool Funding",
            "Withdrawal",
            "Withdrawal Reversal",
            "Reversal",
            "Opening Balance"
        ),
        nullable=False
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False
    )

    status = Column(
        Enum(
            "Pending",
            "Success",
            "Failed",
            "On Hold",
            "Reversed"
        ),
        default="Pending",
        nullable=False
    )

    initiated_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )
    receiver_wallet_id = Column(
        Integer,
        ForeignKey("wallets.id"),
        nullable=True,
        index=True
    )
    original_transaction_id = Column(
        Integer,
        ForeignKey("transactions.id"),
        nullable=True,
        index=True
    )

    idempotency_key = Column(
        String(100),
        nullable=True
    )

    description = Column(
        Text,
        nullable=True
    )

    is_flagged = Column(
        Boolean,
        default=False,
        nullable=False
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