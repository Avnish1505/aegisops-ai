"""Store the plan step's W3C traceparent so one decision is one trace

Revision ID: d4f6a8c0e2b3
Revises: c9e1a3b5d7f2
Create Date: 2026-09-23 22:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4f6a8c0e2b3'
down_revision: str | Sequence[str] | None = 'c9e1a3b5d7f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.add_column(sa.Column('trace_parent', sa.String(length=55), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.drop_column('trace_parent')
