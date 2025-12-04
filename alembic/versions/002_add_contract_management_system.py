"""Add contract management system with documents and waiting list

Revision ID: 002_contract_management
Revises: 001_contract_termination
Create Date: 2025-12-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_contract_management'
down_revision: Union[str, None] = '001_contract_termination'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add capacity to groups table
    op.add_column('groups', sa.Column('capacity', sa.Integer(), nullable=False, server_default='100'))

    # Add contract number allocation fields to contracts table
    op.add_column('contracts', sa.Column('birth_year', sa.Integer(), nullable=True))  # Temporary nullable
    op.add_column('contracts', sa.Column('sequence_number', sa.Integer(), nullable=True))  # Temporary nullable

    # Add document URLs to contracts table
    op.add_column('contracts', sa.Column('passport_copy_url', sa.Text(), nullable=True))
    op.add_column('contracts', sa.Column('form_086_url', sa.Text(), nullable=True))
    op.add_column('contracts', sa.Column('heart_checkup_url', sa.Text(), nullable=True))
    op.add_column('contracts', sa.Column('birth_certificate_url', sa.Text(), nullable=True))
    op.add_column('contracts', sa.Column('contract_images_urls', sa.Text(), nullable=True))

    # Add digital signature fields to contracts table
    op.add_column('contracts', sa.Column('signature_url', sa.Text(), nullable=True))
    op.add_column('contracts', sa.Column('signature_token', sa.String(255), nullable=True))
    op.add_column('contracts', sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('contracts', sa.Column('final_pdf_url', sa.Text(), nullable=True))

    # Add custom fields to contracts table
    op.add_column('contracts', sa.Column('custom_fields', sa.Text(), nullable=True))

    # Add group_id to contracts table
    op.add_column('contracts', sa.Column('group_id', sa.Integer(), nullable=True))

    # Create indexes
    op.create_index('ix_contracts_birth_year', 'contracts', ['birth_year'])
    op.create_index('ix_contracts_signature_token', 'contracts', ['signature_token'], unique=True)

    # Add foreign key for group_id
    op.create_foreign_key(
        'fk_contracts_group_id',
        'contracts',
        'groups',
        ['group_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Update existing contracts with default values (extract birth year from students)
    # This SQL will set birth_year for existing contracts based on student's date_of_birth
    op.execute("""
        UPDATE contracts
        SET birth_year = EXTRACT(YEAR FROM students.date_of_birth)::integer,
            sequence_number = 1
        FROM students
        WHERE contracts.student_id = students.id
        AND contracts.birth_year IS NULL
    """)

    # Now make birth_year and sequence_number NOT NULL
    op.alter_column('contracts', 'birth_year', nullable=False)
    op.alter_column('contracts', 'sequence_number', nullable=False)

    # Create waiting_list table
    op.create_table(
        'waiting_list',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )


def downgrade() -> None:
    # Drop waiting_list table
    op.drop_table('waiting_list')

    # Drop foreign key and group_id column from contracts
    op.drop_constraint('fk_contracts_group_id', 'contracts', type_='foreignkey')
    op.drop_column('contracts', 'group_id')

    # Drop indexes
    op.drop_index('ix_contracts_signature_token', 'contracts')
    op.drop_index('ix_contracts_birth_year', 'contracts')

    # Drop contract document and signature columns
    op.drop_column('contracts', 'custom_fields')
    op.drop_column('contracts', 'final_pdf_url')
    op.drop_column('contracts', 'signed_at')
    op.drop_column('contracts', 'signature_token')
    op.drop_column('contracts', 'signature_url')
    op.drop_column('contracts', 'contract_images_urls')
    op.drop_column('contracts', 'birth_certificate_url')
    op.drop_column('contracts', 'heart_checkup_url')
    op.drop_column('contracts', 'form_086_url')
    op.drop_column('contracts', 'passport_copy_url')
    op.drop_column('contracts', 'sequence_number')
    op.drop_column('contracts', 'birth_year')

    # Drop capacity column from groups
    op.drop_column('groups', 'capacity')
