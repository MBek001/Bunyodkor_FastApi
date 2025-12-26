"""make group identifier unique for non-deleted

Revision ID: 001
Revises:
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Drop the existing unique index on identifier and create a partial unique index
    that only enforces uniqueness for non-deleted groups.
    """
    # Drop existing unique index if it exists
    op.drop_index('ix_groups_identifier', table_name='groups', if_exists=True)

    # Create partial unique index: unique only for non-DELETED groups
    op.execute("""
        CREATE UNIQUE INDEX ix_groups_identifier_active
        ON groups (identifier)
        WHERE status != 'DELETED'
    """)


def downgrade():
    """
    Revert to the original unique index (without the WHERE clause).
    """
    # Drop the partial unique index
    op.drop_index('ix_groups_identifier_active', table_name='groups', if_exists=True)

    # Recreate the original unique index
    op.create_index('ix_groups_identifier', 'groups', ['identifier'], unique=True)
