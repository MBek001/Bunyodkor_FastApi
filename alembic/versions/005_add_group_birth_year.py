"""Add birth_year to Group model

Revision ID: 005_group_birth_year
Revises: 004_archived_status
Create Date: 2025-12-09 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_group_birth_year'
down_revision: Union[str, None] = '004_archived_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add birth_year to groups table.
    This specifies which birth year students the group is designed for.
    Example: "Kattalar guruhi 2017" would have birth_year=2017
    """
    # Add birth_year column (temporarily nullable for existing data)
    op.add_column('groups', sa.Column('birth_year', sa.Integer(), nullable=True))

    # Set default birth_year=2015 for existing groups (you can update manually later)
    op.execute("UPDATE groups SET birth_year = 2015 WHERE birth_year IS NULL")

    # Make it NOT NULL
    op.alter_column('groups', 'birth_year', nullable=False)

    # Add index
    op.create_index('ix_groups_birth_year', 'groups', ['birth_year'])


def downgrade() -> None:
    """Remove birth_year from groups"""
    op.drop_index('ix_groups_birth_year', 'groups')
    op.drop_column('groups', 'birth_year')
