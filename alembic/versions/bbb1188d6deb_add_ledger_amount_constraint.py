"""add ledger amount constraint

Revision ID: bbb1188d6deb
Revises: 39e95fdc4e7f
Create Date: 2026-11-02 16:13:16.969253

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbb1188d6deb'
down_revision: Union[str, Sequence[str], None] = '39e95fdc4e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_ledger_entry_amount_positive",
        "ledger_entries",
        "amount > 0"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ledger_entry_amount_positive",
        "ledger_entries",
        type_="check"
    )