"""Persist the full decision record

Revision ID: 5c1f0e2a9b41
Revises: 124aba1dcba2
Create Date: 2026-09-23 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5c1f0e2a9b41'
down_revision: str | Sequence[str] | None = '124aba1dcba2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the scenario, plan, findings, evidence and model provenance to decisions."""
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.add_column(sa.Column('scenario', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('scenario_sha256', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('assignments', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('unmet_requirements', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('safety_findings', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('evidence', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('prompt_version', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('model_version', sa.String(length=200), nullable=True))
        batch_op.create_index('idx_decision_scenario_sha256', ['scenario_sha256'], unique=False)


def downgrade() -> None:
    """Drop the full-record columns."""
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.drop_index('idx_decision_scenario_sha256')
        batch_op.drop_column('model_version')
        batch_op.drop_column('prompt_version')
        batch_op.drop_column('evidence')
        batch_op.drop_column('safety_findings')
        batch_op.drop_column('unmet_requirements')
        batch_op.drop_column('assignments')
        batch_op.drop_column('scenario_sha256')
        batch_op.drop_column('scenario')
