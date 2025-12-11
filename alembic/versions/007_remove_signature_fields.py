"""Remove signature fields from contracts table

Revision ID: 007_remove_signature_fields
Revises: 006_waiting_list_independent
Create Date: 2025-12-11 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007_remove_signature_fields'
down_revision: Union[str, None] = '006_waiting_list_independent'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove unused signature-related fields from contracts table:
    - signature_url
    - signature_token
    - signed_at

    These fields are no longer used as PDFs are generated immediately
    without requiring digital signatures.
    """
    # Drop the unique index on signature_token first
    op.drop_index('ix_contracts_signature_token', table_name='contracts')

    # Drop the signature columns
    op.drop_column('contracts', 'signed_at')
    op.drop_column('contracts', 'signature_token')
    op.drop_column('contracts', 'signature_url')


def downgrade() -> None:
    """
    Restore signature fields to contracts table.

    WARNING: This will restore the columns but data will be lost!
    """
    # Add back the signature columns
    op.add_column('contracts', sa.Column('signature_url', sa.Text(), nullable=True))
    op.add_column('contracts', sa.Column('signature_token', sa.String(255), nullable=True))
    op.add_column('contracts', sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True))

    # Recreate the index
    op.create_index('ix_contracts_signature_token', 'contracts', ['signature_token'], unique=True)
