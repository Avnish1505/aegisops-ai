"""WGS84: PostGIS extension and incidents.location as geography(Point, 4326)

Revision ID: f2b8d4e6a913
Revises: e5a7c9d2f104
Create Date: 2026-09-23 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.db.types import GeoPoint

# revision identifiers, used by Alembic.
revision: str = 'f2b8d4e6a913'
down_revision: str | Sequence[str] | None = 'e5a7c9d2f104'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    rows = bind.execute(sa.text("SELECT COUNT(*) FROM incidents")).scalar_one()
    if rows:
        # Synthetic 0-100 grid coordinates have no geographic meaning; refuse to invent positions.
        raise RuntimeError(
            f"incidents holds {rows} rows with grid coordinates that cannot be converted to WGS84; "
            "export and clear them before upgrading."
        )
    op.drop_index('idx_incident_location', table_name='incidents')
    with op.batch_alter_table('incidents') as batch_op:
        batch_op.drop_column('location_x')
        batch_op.drop_column('location_y')
        batch_op.add_column(sa.Column('location', GeoPoint(), nullable=False))
    op.create_index(
        'idx_incident_location', 'incidents', ['location'], unique=False, postgresql_using='gist'
    )


def downgrade() -> None:
    op.drop_index('idx_incident_location', table_name='incidents')
    with op.batch_alter_table('incidents') as batch_op:
        batch_op.drop_column('location')
        batch_op.add_column(sa.Column('location_x', sa.Float(), nullable=False))
        batch_op.add_column(sa.Column('location_y', sa.Float(), nullable=False))
    op.create_index(
        'idx_incident_location', 'incidents', ['location_x', 'location_y'], unique=False
    )
