from alembic import op
import sqlalchemy as sa


revision = "f77467001cd9"
down_revision = "69e29cdc2461"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "accounts",
        "account_type",
        existing_type=sa.Enum(
            "User Wallet",
            "Merchant Wallet",
            "Bank Settlement",
            "Cashback Pool",
            "Fees",
            "Withdrawal Clearing",
            "Hold"
        ),
        type_=sa.Enum(
            "User Wallet",
            "Merchant Wallet",
            "Bank Settlement",
            "Cashback Pool",
            "Fees",
            "Withdrawal Clearing",
            "Hold",
            "Opening Equity"
        ),
        existing_nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        "accounts",
        "account_type",
        existing_type=sa.Enum(
            "User Wallet",
            "Merchant Wallet",
            "Bank Settlement",
            "Cashback Pool",
            "Fees",
            "Withdrawal Clearing",
            "Hold",
            "Opening Equity"
        ),
        type_=sa.Enum(
            "User Wallet",
            "Merchant Wallet",
            "Bank Settlement",
            "Cashback Pool",
            "Fees",
            "Withdrawal Clearing",
            "Hold"
        ),
        existing_nullable=False
    )