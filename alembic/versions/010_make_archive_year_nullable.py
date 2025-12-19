"""make archive_year nullable

Revision ID: 010
Revises: 009
Create Date: 2025-12-20
"""
from alembic import op
import sqlalchemy as sa

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make archive_year nullable in students table
    op.alter_column('students', 'archive_year',
                    existing_type=sa.Integer(),
                    nullable=True,
                    server_default=None)

    # Make archive_year nullable in groups table
    op.alter_column('groups', 'archive_year',
                    existing_type=sa.Integer(),
                    nullable=True,
                    server_default=None)

    # Make archive_year nullable in contracts table
    op.alter_column('contracts', 'archive_year',
                    existing_type=sa.Integer(),
                    nullable=True,
                    server_default=None)

    # Set existing archive_year values to NULL where they are 2025 (the default)
    # This is optional - comment out if you want to keep existing values
    # op.execute("UPDATE students SET archive_year = NULL WHERE archive_year = 2025")
    # op.execute("UPDATE groups SET archive_year = NULL WHERE archive_year = 2025")
    # op.execute("UPDATE contracts SET archive_year = NULL WHERE archive_year = 2025")


def downgrade() -> None:
    # Make archive_year not nullable again and restore default
    op.alter_column('students', 'archive_year',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='2025')

    op.alter_column('groups', 'archive_year',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='2025')

    op.alter_column('contracts', 'archive_year',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='2025')
