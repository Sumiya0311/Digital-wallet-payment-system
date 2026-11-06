from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "c0afe93a462c"
down_revision = "f77467001cd9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve Opening Equity and add Opening Balance.
    op.alter_column(
        "transactions",
        "type",
        existing_type=mysql.ENUM(
            "Add Money",
            "P2P Transfer",
            "Merchant Payment",
            "Merchant Refund",
            "Cashback",
            "Withdrawal",
            "Withdrawal Reversal",
            "Reversal"
        ),
        type_=mysql.ENUM(
            "Add Money",
            "P2P Transfer",
            "Merchant Payment",
            "Merchant Refund",
            "Cashback",
            "Withdrawal",
            "Withdrawal Reversal",
            "Reversal",
            "Opening Balance"
        ),
        existing_nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        "transactions",
        "type",
        existing_type=mysql.ENUM(
            "Add Money",
            "P2P Transfer",
            "Merchant Payment",
            "Merchant Refund",
            "Cashback",
            "Withdrawal",
            "Withdrawal Reversal",
            "Reversal",
            "Opening Balance"
        ),
        type_=mysql.ENUM(
            "Add Money",
            "P2P Transfer",
            "Merchant Payment",
            "Merchant Refund",
            "Cashback",
            "Withdrawal",
            "Withdrawal Reversal",
            "Reversal"
        ),
        existing_nullable=False
    )