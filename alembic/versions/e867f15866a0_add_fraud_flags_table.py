"""add fraud flags table

Revision ID: e867f15866a0
Revises: 91ad1db8fe45
Create Date: 2026-11-05 19:58:21.198455
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e867f15866a0"
down_revision: Union[str, Sequence[str], None] = "91ad1db8fe45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create fraud flags table."""

    op.create_table(
        "fraud_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "Pending",
                "Approved",
                "Rejected",
                name="fraud_flag_status",
            ),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_fraud_flags_id",
        "fraud_flags",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_fraud_flags_transaction_id",
        "fraud_flags",
        ["transaction_id"],
        unique=False,
    )

    op.create_index(
        "ix_fraud_flags_user_id",
        "fraud_flags",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove fraud flags table."""

    op.drop_index(
        "ix_fraud_flags_user_id",
        table_name="fraud_flags",
    )

    op.drop_index(
        "ix_fraud_flags_transaction_id",
        table_name="fraud_flags",
    )

    op.drop_index(
        "ix_fraud_flags_id",
        table_name="fraud_flags",
    )

    op.drop_table("fraud_flags")