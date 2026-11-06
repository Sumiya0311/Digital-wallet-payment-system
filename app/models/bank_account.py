from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint
)

from app.database import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "account_number",
            name="uq_bank_account_user_number"
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    account_holder_name = Column(
        String(100),
        nullable=False
    )

    bank_name = Column(
        String(100),
        nullable=False
    )

    account_number = Column(
        String(18),
        nullable=False
    )

    ifsc_code = Column(
        String(11),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
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

    @property
    def masked_account_number(self):
        return "*" * max(0, len(self.account_number) - 4) + self.account_number[-4:]