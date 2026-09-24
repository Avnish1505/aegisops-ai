"""Saved exercise scenarios

Revision ID: b8d0f2a4c6e3
Revises: a4c6e8f0b2d1
Create Date: 2026-09-23 19:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8d0f2a4c6e3'
down_revision: str | Sequence[str] | None = 'a4c6e8f0b2d1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'exercises',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('scenario', sa.JSON(), nullable=False),
        sa.Column('scenario_sha256', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('exercises')
