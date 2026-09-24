"""User-study sessions and tasks

Revision ID: c3e5a7b9d1f4
Revises: b2d4f6a8c0e1
Create Date: 2026-09-24 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3e5a7b9d1f4'
down_revision: str | Sequence[str] | None = 'b2d4f6a8c0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'study_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('participant', sa.String(length=32), nullable=False),
        sa.Column('participant_number', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('participant'),
    )
    op.create_table(
        'study_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('ui', sa.String(length=16), nullable=False),
        sa.Column('task_key', sa.String(length=8), nullable=False),
        sa.Column('injected_error', sa.String(length=32), nullable=True),
        sa.Column('expected_action', sa.String(length=16), nullable=False),
        sa.Column('expected_reason', sa.String(length=64), nullable=True),
        sa.Column('decision_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.id']),
        sa.ForeignKeyConstraint(['session_id'], ['study_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_study_task_session', 'study_tasks', ['session_id', 'order'])


def downgrade() -> None:
    op.drop_index('idx_study_task_session', table_name='study_tasks')
    op.drop_table('study_tasks')
    op.drop_table('study_sessions')
