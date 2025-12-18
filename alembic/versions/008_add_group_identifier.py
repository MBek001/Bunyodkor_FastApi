"""add group identifier

Revision ID: 008
Revises: 007
Create Date: 2025-12-18

"""
from alembic import op
import sqlalchemy as sa


revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('groups', sa.Column('identifier', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_groups_identifier'), 'groups', ['identifier'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_groups_identifier'), table_name='groups')
    op.drop_column('groups', 'identifier')
