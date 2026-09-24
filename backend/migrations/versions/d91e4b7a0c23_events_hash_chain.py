"""Hash-chained events table

Revision ID: d91e4b7a0c23
Revises: c3f8a2e61d57
Create Date: 2026-09-23 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd91e4b7a0c23'
down_revision: str | Sequence[str] | None = 'c3f8a2e61d57'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Append-only audit events; prev_hash is unique so the chain cannot fork."""
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('ts', sa.String(length=40), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('prev_hash', sa.String(length=64), nullable=False),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hash'),
        sa.UniqueConstraint('prev_hash'),
    )
    op.create_index('idx_event_type', 'events', ['type'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_event_type', table_name='events')
    op.drop_table('events')
