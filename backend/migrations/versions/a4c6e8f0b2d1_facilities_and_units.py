"""OSM facilities and the units stationed at them

Revision ID: a4c6e8f0b2d1
Revises: f2b8d4e6a913
Create Date: 2026-09-23 19:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.db.types import GeoPoint

# revision identifiers, used by Alembic.
revision: str = 'a4c6e8f0b2d1'
down_revision: str | Sequence[str] | None = 'f2b8d4e6a913'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'facilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('osm_type', sa.String(length=8), nullable=False),
        sa.Column('osm_id', sa.BigInteger(), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('location', GeoPoint(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('osm_type', 'osm_id', name='uq_facility_osm'),
    )
    op.create_index('idx_facility_kind', 'facilities', ['kind'], unique=False)
    op.create_index(
        'idx_facility_location', 'facilities', ['location'], unique=False,
        postgresql_using='gist',
    )
    op.create_table(
        'units',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('location', GeoPoint(), nullable=False),
        sa.Column('available', sa.Boolean(), nullable=False),
        sa.Column('speed_kmh', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['facility_id'], ['facilities.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('units')
    op.drop_index('idx_facility_location', table_name='facilities')
    op.drop_index('idx_facility_kind', table_name='facilities')
    op.drop_table('facilities')
