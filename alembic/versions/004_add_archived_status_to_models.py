"""Add ARCHIVED status to models for yearly archiving

Revision ID: 004_archived_status
Revises: 003_archive_year
Create Date: 2025-12-09 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_archived_status'
down_revision: Union[str, None] = '003_archive_year'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add status field to groups table and ARCHIVED status to enums.
    This enables yearly archiving of all data.
    """
    # Add status column to groups table
    op.add_column('groups', sa.Column('status', sa.String(20), nullable=False, server_default='active'))
    op.create_index('ix_groups_status', 'groups', ['status'])

    # Note: StudentStatus and ContractStatus already have columns, we just extended the enum values
    # SQLAlchemy string-based enums don't require migration for new values


def downgrade() -> None:
    """Remove status field from groups"""
    op.drop_index('ix_groups_status', 'groups')
    op.drop_column('groups', 'status')
