from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Enum,
    CheckConstraint,
    UniqueConstraint
)

from app.database import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_ledger_entry_amount_positive"
        ),
        UniqueConstraint(
            "transaction_id",
            "account_id",
            name="uq_ledger_entry_transaction_account"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    transaction_id = Column(
        Integer,
        ForeignKey("transactions.id"),
        nullable=False,
        index=True
    )

    account_id = Column(
        Integer,
        ForeignKey("accounts.id"),
        nullable=False,
        index=True
    )

    entry_type = Column(
        Enum("Debit", "Credit"),
        nullable=False
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False
    )

    balance_after = Column(
        Numeric(12, 2),
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