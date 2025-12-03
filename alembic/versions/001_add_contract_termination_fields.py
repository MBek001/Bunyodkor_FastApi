"""Add contract termination fields

Revision ID: 001_contract_termination
Revises:
Create Date: 2025-12-03 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_contract_termination'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add termination fields to contracts table
    op.add_column('contracts', sa.Column('terminated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('contracts', sa.Column('terminated_by_user_id', sa.Integer(), nullable=True))
    op.add_column('contracts', sa.Column('termination_reason', sa.Text(), nullable=True))

    # Add foreign key constraint for terminated_by_user_id
    op.create_foreign_key(
        'fk_contracts_terminated_by_user_id',
        'contracts',
        'users',
        ['terminated_by_user_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint('fk_contracts_terminated_by_user_id', 'contracts', type_='foreignkey')

    # Remove termination columns
    op.drop_column('contracts', 'termination_reason')
    op.drop_column('contracts', 'terminated_by_user_id')
    op.drop_column('contracts', 'terminated_at')
