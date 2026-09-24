"""Store intake reports, their grounded readings and the operator's review

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2
Create Date: 2026-09-24 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2d4f6a8c0e1'
down_revision: str | Sequence[str] | None = 'a1c3e5f7b9d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'intake_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('candidate', sa.JSON(), nullable=True),
        sa.Column('read_meta', sa.JSON(), nullable=True),
        sa.Column('review_reasons', sa.JSON(), nullable=False),
        sa.Column('confirmed_fields', sa.JSON(), nullable=True),
        sa.Column('edited_fields', sa.JSON(), nullable=True),
        sa.Column('reviewed_by', sa.String(length=255), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('merged_into', sa.Integer(), nullable=True),
        sa.Column('incident_id', sa.String(length=64), nullable=True),
        sa.Column('exercise_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['merged_into'], ['intake_reports.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_intake_status', 'intake_reports', ['status'])


def downgrade() -> None:
    op.drop_index('idx_intake_status', table_name='intake_reports')
    op.drop_table('intake_reports')
