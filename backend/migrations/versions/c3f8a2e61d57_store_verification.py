"""Store verification, drafts, constraints and travel times with each decision

Revision ID: c3f8a2e61d57
Revises: b7e4c1d9f3a2
Create Date: 2026-09-23 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3f8a2e61d57'
down_revision: str | Sequence[str] | None = 'b7e4c1d9f3a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    ('verification', sa.JSON()),
    ('drafts', sa.JSON()),
    ('constraints', sa.JSON()),
    ('travel_times', sa.JSON()),
    ('objective', sa.Float()),
    ('reference_objective', sa.Float()),
    ('solve_status', sa.String(length=32)),
    ('infeasibility', sa.JSON()),
)


def upgrade() -> None:
    """Keep what the verifier saw and concluded, so a decision can be replayed and re-verified."""
    with op.batch_alter_table('decisions') as batch_op:
        for name, column_type in COLUMNS:
            batch_op.add_column(sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('decisions') as batch_op:
        for name, _ in reversed(COLUMNS):
            batch_op.drop_column(name)
