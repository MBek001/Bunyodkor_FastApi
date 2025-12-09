"""Add archive_year to Group, Student, Contract for yearly data separation

Revision ID: 003_archive_year
Revises: 002_contract_management
Create Date: 2025-12-09 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '003_archive_year'
down_revision: Union[str, None] = '002_contract_management'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add archive_year column to groups, students, and contracts tables.
    This allows yearly data separation (2025, 2026, 2027, etc.)
    """
    current_year = datetime.now().year

    # Add archive_year to groups table
    op.add_column('groups', sa.Column('archive_year', sa.Integer(), nullable=False, server_default=str(current_year)))
    op.create_index('ix_groups_archive_year', 'groups', ['archive_year'])

    # Add archive_year to students table
    op.add_column('students', sa.Column('archive_year', sa.Integer(), nullable=False, server_default=str(current_year)))
    op.create_index('ix_students_archive_year', 'students', ['archive_year'])

    # Add archive_year to contracts table
    op.add_column('contracts', sa.Column('archive_year', sa.Integer(), nullable=False, server_default=str(current_year)))
    op.create_index('ix_contracts_archive_year', 'contracts', ['archive_year'])


def downgrade() -> None:
    """Remove archive_year columns"""
    # Drop indexes first
    op.drop_index('ix_contracts_archive_year', 'contracts')
    op.drop_index('ix_students_archive_year', 'students')
    op.drop_index('ix_groups_archive_year', 'groups')

    # Drop columns
    op.drop_column('contracts', 'archive_year')
    op.drop_column('students', 'archive_year')
    op.drop_column('groups', 'archive_year')
