"""Record every hazard-feed poll (success or failure) for feed health

Revision ID: e7a9c1b3d5f6
Revises: d4f6a8c0e2b3
Create Date: 2026-09-24 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7a9c1b3d5f6'
down_revision: str | Sequence[str] | None = 'd4f6a8c0e2b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'feed_polls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('polled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ok', sa.Boolean(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('fetched', sa.Integer(), nullable=False),
        sa.Column('inserted', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_feed_poll_source_time', 'feed_polls', ['source', 'polled_at'])


def downgrade() -> None:
    op.drop_index('idx_feed_poll_source_time', table_name='feed_polls')
    op.drop_table('feed_polls')
