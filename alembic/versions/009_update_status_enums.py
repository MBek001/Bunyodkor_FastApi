"""update status enums

Revision ID: 009
Revises: 008
Create Date: 2025-12-18
"""
from alembic import op
import sqlalchemy as sa

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add DELETED to UserStatus
    op.execute("ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'deleted'")

    # Add DELETED to StudentStatus
    op.execute("ALTER TYPE studentstatus ADD VALUE IF NOT EXISTS 'deleted'")

    # Add DELETED to ContractStatus
    op.execute("ALTER TYPE contractstatus ADD VALUE IF NOT EXISTS 'deleted'")

    # Update existing GRADUATED students to ARCHIVED
    op.execute("UPDATE students SET status = 'archived' WHERE status = 'graduated'")

    # Update existing DROPPED students to DELETED
    op.execute("UPDATE students SET status = 'deleted' WHERE status = 'dropped'")

    # Update existing SUSPENDED students to DELETED
    op.execute("UPDATE students SET status = 'deleted' WHERE status = 'suspended'")

    # Update existing TERMINATED contracts to DELETED
    op.execute("UPDATE contracts SET status = 'deleted' WHERE status = 'terminated'")

    # Update existing PENDING contracts to ACTIVE
    op.execute("UPDATE contracts SET status = 'active' WHERE status = 'pending'")


def downgrade() -> None:
    # Update back to old statuses (best effort)
    op.execute("UPDATE students SET status = 'graduated' WHERE status = 'archived'")
    op.execute("UPDATE students SET status = 'dropped' WHERE status = 'deleted'")
    op.execute("UPDATE contracts SET status = 'terminated' WHERE status = 'deleted'")

    # Note: Cannot remove enum values in PostgreSQL easily
    # Would need to recreate the entire enum type
