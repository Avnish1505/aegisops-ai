"""Rename decisions.advisory_confidence to coverage

Revision ID: 8d3a6b7c2e10
Revises: 5c1f0e2a9b41
Create Date: 2026-09-23 12:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8d3a6b7c2e10'
down_revision: str | Sequence[str] | None = '5c1f0e2a9b41'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """The value is the share of required units assigned, not a confidence; name it so."""
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.alter_column(
            'advisory_confidence',
            new_column_name='coverage',
            existing_type=sa.Float(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Restore the previous column name."""
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.alter_column(
            'coverage',
            new_column_name='advisory_confidence',
            existing_type=sa.Float(),
            existing_nullable=False,
        )
