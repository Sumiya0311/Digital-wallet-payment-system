"""add receiver wallet id to transactions

Revision ID: 8f104ae346b3
Revises: e867f15866a0
Create Date: 2026-11-06 10:46:47.404880
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f104ae346b3"
down_revision: Union[str, Sequence[str], None] = "e867f15866a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "receiver_wallet_id",
            sa.Integer(),
            nullable=True
        )
    )

    op.create_index(
        "ix_transactions_receiver_wallet_id",
        "transactions",
        ["receiver_wallet_id"],
        unique=False
    )

    op.create_foreign_key(
        "fk_transactions_receiver_wallet_id",
        "transactions",
        "wallets",
        ["receiver_wallet_id"],
        ["id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_transactions_receiver_wallet_id",
        "transactions",
        type_="foreignkey"
    )

    op.drop_index(
        "ix_transactions_receiver_wallet_id",
        table_name="transactions"
    )

    op.drop_column(
        "transactions",
        "receiver_wallet_id"
    )