"""Ingested hazard alerts (SACHET CAP, USGS, GDACS)

Revision ID: c9e1a3b5d7f2
Revises: b8d0f2a4c6e3
Create Date: 2026-09-23 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.db.types import GeoPoint

# revision identifiers, used by Alembic.
revision: str = 'c9e1a3b5d7f2'
down_revision: str | Sequence[str] | None = 'b8d0f2a4c6e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('identifier', sa.String(length=255), nullable=False),
        sa.Column('source_ref', sa.String(length=255), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event', sa.String(length=255), nullable=True),
        sa.Column('severity', sa.String(length=32), nullable=True),
        sa.Column('headline', sa.Text(), nullable=True),
        sa.Column('area_desc', sa.Text(), nullable=True),
        sa.Column('location', GeoPoint(), nullable=True),
        sa.Column('raw_payload', sa.Text(), nullable=False),
        sa.Column('parsed', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'identifier', name='uq_alert_source_identifier'),
    )
    op.create_index('idx_alert_source_ref', 'alerts', ['source', 'source_ref'], unique=False)
    op.create_index('idx_alert_sent_at', 'alerts', ['sent_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_alert_sent_at', table_name='alerts')
    op.drop_index('idx_alert_source_ref', table_name='alerts')
    op.drop_table('alerts')
