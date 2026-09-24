"""A reason code on every disposition

Revision ID: f8b0d2c4e6a7
Revises: e7a9c1b3d5f6
Create Date: 2026-09-24 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f8b0d2c4e6a7'
down_revision: str | Sequence[str] | None = 'e7a9c1b3d5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('approvals') as batch_op:
        batch_op.add_column(sa.Column('reason_code', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('approvals') as batch_op:
        batch_op.drop_column('reason_code')
