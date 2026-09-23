"""Record the proposer's token subject; widen usernames to hold OIDC subjects

Revision ID: e5a7c9d2f104
Revises: d91e4b7a0c23
Create Date: 2026-09-23 17:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5a7c9d2f104'
down_revision: str | Sequence[str] | None = 'd91e4b7a0c23'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.add_column(sa.Column('proposer_sub', sa.String(length=255), nullable=True))
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'username', existing_type=sa.String(length=50), type_=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'username', existing_type=sa.String(length=255), type_=sa.String(length=50),
            existing_nullable=False,
        )
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.drop_column('proposer_sub')
