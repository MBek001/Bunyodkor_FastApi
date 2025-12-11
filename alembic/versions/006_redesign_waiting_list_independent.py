"""Redesign waiting list to be independent from students table

Revision ID: 006_waiting_list_independent
Revises: 005_group_birth_year
Create Date: 2025-12-11 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_waiting_list_independent'
down_revision: Union[str, None] = '005_group_birth_year'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Redesign waiting_list table to be independent from students table.

    Changes:
    - Remove student_id foreign key
    - Add student_first_name, student_last_name, birth_year
    - Add father_name, father_phone, mother_name, mother_phone
    """
    # Step 1: Add new columns as nullable (to handle existing data)
    op.add_column('waiting_list', sa.Column('student_first_name', sa.String(100), nullable=True))
    op.add_column('waiting_list', sa.Column('student_last_name', sa.String(100), nullable=True))
    op.add_column('waiting_list', sa.Column('birth_year', sa.Integer(), nullable=True))
    op.add_column('waiting_list', sa.Column('father_name', sa.String(200), nullable=True))
    op.add_column('waiting_list', sa.Column('father_phone', sa.String(20), nullable=True))
    op.add_column('waiting_list', sa.Column('mother_name', sa.String(200), nullable=True))
    op.add_column('waiting_list', sa.Column('mother_phone', sa.String(20), nullable=True))

    # Step 2: Migrate existing data from students table to waiting_list
    # Copy student names and calculate birth_year from students table
    op.execute("""
        UPDATE waiting_list wl
        SET
            student_first_name = s.first_name,
            student_last_name = s.last_name,
            birth_year = EXTRACT(YEAR FROM s.date_of_birth)::INTEGER
        FROM students s
        WHERE wl.student_id = s.id
    """)

    # Try to populate parent info from parents table if available
    op.execute("""
        UPDATE waiting_list wl
        SET
            father_name = COALESCE(
                (SELECT first_name || ' ' || last_name
                 FROM parents
                 WHERE student_id = wl.student_id
                 AND (relationship_type = 'father' OR relationship_type IS NULL)
                 LIMIT 1),
                'Unknown'
            ),
            father_phone = COALESCE(
                (SELECT phone
                 FROM parents
                 WHERE student_id = wl.student_id
                 AND (relationship_type = 'father' OR relationship_type IS NULL)
                 LIMIT 1),
                '---'
            )
    """)

    # Set default values for any remaining NULL fields
    op.execute("UPDATE waiting_list SET student_first_name = 'Unknown' WHERE student_first_name IS NULL")
    op.execute("UPDATE waiting_list SET student_last_name = 'Student' WHERE student_last_name IS NULL")
    op.execute("UPDATE waiting_list SET birth_year = 2020 WHERE birth_year IS NULL")

    # Step 3: Make required columns NOT NULL
    op.alter_column('waiting_list', 'student_first_name', nullable=False)
    op.alter_column('waiting_list', 'student_last_name', nullable=False)
    op.alter_column('waiting_list', 'birth_year', nullable=False)

    # Step 4: Add index on birth_year for faster queries
    op.create_index('ix_waiting_list_birth_year', 'waiting_list', ['birth_year'])

    # Step 5: Drop the foreign key constraint and student_id column
    # Note: Foreign key constraint name may vary - adjust if needed
    op.drop_constraint('waiting_list_student_id_fkey', 'waiting_list', type_='foreignkey')
    op.drop_column('waiting_list', 'student_id')


def downgrade() -> None:
    """
    Revert waiting_list table back to linked students model.

    WARNING: This will lose parent information stored in waiting list!
    """
    # Add back student_id column
    op.add_column('waiting_list', sa.Column('student_id', sa.Integer(), nullable=True))

    # Try to match waiting list entries back to students by name and birth year
    # This is best-effort only and may not work perfectly
    op.execute("""
        UPDATE waiting_list wl
        SET student_id = (
            SELECT s.id
            FROM students s
            WHERE s.first_name = wl.student_first_name
            AND s.last_name = wl.student_last_name
            AND EXTRACT(YEAR FROM s.date_of_birth) = wl.birth_year
            LIMIT 1
        )
    """)

    # Remove entries that couldn't be matched (to avoid NULL constraint violation)
    op.execute("DELETE FROM waiting_list WHERE student_id IS NULL")

    # Make student_id NOT NULL and add back foreign key
    op.alter_column('waiting_list', 'student_id', nullable=False)
    op.create_foreign_key(
        'waiting_list_student_id_fkey',
        'waiting_list',
        'students',
        ['student_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Drop new columns
    op.drop_index('ix_waiting_list_birth_year', 'waiting_list')
    op.drop_column('waiting_list', 'mother_phone')
    op.drop_column('waiting_list', 'mother_name')
    op.drop_column('waiting_list', 'father_phone')
    op.drop_column('waiting_list', 'father_name')
    op.drop_column('waiting_list', 'birth_year')
    op.drop_column('waiting_list', 'student_last_name')
    op.drop_column('waiting_list', 'student_first_name')
