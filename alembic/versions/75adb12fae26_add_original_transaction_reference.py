"""add original transaction reference

Revision ID: 75adb12fae26
Revises: c0afe93a462c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '75adb12fae26'
down_revision: Union[str, Sequence[str], None] = 'c0afe93a462c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'transactions',
        sa.Column(
            'original_transaction_id',
            sa.Integer(),
            nullable=True
        )
    )

    op.create_index(
        'ix_transactions_original_transaction_id',
        'transactions',
        ['original_transaction_id'],
        unique=False
    )

    op.create_foreign_key(
        'fk_transactions_original_transaction_id',
        'transactions',
        'transactions',
        ['original_transaction_id'],
        ['id']
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_transactions_original_transaction_id',
        'transactions',
        type_='foreignkey'
    )

    op.drop_index(
        'ix_transactions_original_transaction_id',
        table_name='transactions'
    )

    op.drop_column(
        'transactions',
        'original_transaction_id'
    )