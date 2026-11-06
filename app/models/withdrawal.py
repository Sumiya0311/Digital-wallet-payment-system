from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint
)

from app.database import Base


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            name="uq_withdrawal_transaction_id"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    transaction_id = Column(
        Integer,
        ForeignKey("transactions.id"),
        nullable=False,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    bank_account_id = Column(
        Integer,
        ForeignKey("bank_accounts.id"),
        nullable=False
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False
    )

    status = Column(
        Enum("Pending", "Completed", "Failed"),
        default="Pending",
        nullable=False,
        index=True
    )

    failure_reason = Column(Text, nullable=True)

    processed_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )