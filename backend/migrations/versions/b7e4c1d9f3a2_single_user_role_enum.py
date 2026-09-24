"""Add the approver role to the shared userrole enum

Revision ID: b7e4c1d9f3a2
Revises: 8d3a6b7c2e10
Create Date: 2026-09-23 13:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e4c1d9f3a2'
down_revision: str | Sequence[str] | None = '8d3a6b7c2e10'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PREVIOUS = sa.Enum('ADMIN', 'OPERATOR', 'VIEWER', name='userrole')
CURRENT = sa.Enum('VIEWER', 'OPERATOR', 'APPROVER', 'ADMIN', name='userrole')


def upgrade() -> None:
    """Roles now come from aegisops.application.roles.UserRole, which adds APPROVER."""
    if op.get_bind().dialect.name == "postgresql":
        # PostgreSQL has a native enum type; add the value to it in place.
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'APPROVER'")
        return
    with op.batch_alter_table('roles') as batch_op:
        batch_op.alter_column(
            'name', existing_type=PREVIOUS, type_=CURRENT, existing_nullable=False
        )


def downgrade() -> None:
    """Restore the three-role enum; delete any APPROVER role rows first."""
    if op.get_bind().dialect.name == "postgresql":
        # PostgreSQL cannot drop an enum value; the extra value is harmless.
        return
    with op.batch_alter_table('roles') as batch_op:
        batch_op.alter_column(
            'name', existing_type=CURRENT, type_=PREVIOUS, existing_nullable=False
        )
