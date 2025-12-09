"""
Contract number allocation service.

Handles contract number generation based on student birth year and group capacity.
Format: N{sequence}{year}
Examples: N12020, N22020, N32020 for students born in 2020
          N12012, N22012, N32012 for students born in 2012

When a contract is canceled, the number becomes available for reuse.
"""
from datetime import date
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.domain import Contract, Group, Student
from app.models.enums import ContractStatus
from typing import Optional, List


class ContractNumberAllocationError(Exception):
    """Raised when contract number allocation fails"""
    pass


async def get_available_contract_numbers(
    db: AsyncSession,
    group_id: int,
    birth_year: int,
    archive_year: Optional[int] = None
) -> List[int]:
    """
    Get list of available contract numbers for a group and birth year.

    Returns list of available sequence numbers (1 to group capacity).
    Empty slots (from canceled contracts) are included.

    Args:
        db: Database session
        group_id: Group ID
        birth_year: Student's birth year
        archive_year: Archive year filter (defaults to current year)

    Returns:
        List of available sequence numbers
    """
    from datetime import datetime
    if archive_year is None:
        archive_year = datetime.now().year

    # Get group capacity
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group = group_result.scalar_one_or_none()

    if not group:
        raise ContractNumberAllocationError(f"Group with ID {group_id} not found")

    # Get all used sequence numbers for this birth year in this group for the archive year
    contracts_result = await db.execute(
        select(Contract.sequence_number).where(
            and_(
                Contract.group_id == group_id,
                Contract.birth_year == birth_year,
                Contract.archive_year == archive_year,
                or_(
                    Contract.status == ContractStatus.ACTIVE,
                    Contract.status == ContractStatus.EXPIRED
                )
            )
        )
    )
    used_sequences = set(row[0] for row in contracts_result.fetchall())

    # Find available sequences (1 to capacity)
    all_sequences = set(range(1, group.capacity + 1))
    available_sequences = sorted(all_sequences - used_sequences)

    return available_sequences


async def allocate_contract_number(
    db: AsyncSession,
    student_id: int,
    group_id: int
) -> tuple[str, int, int]:
    """
    Allocate a contract number for a student in a group.

    Returns the contract number string, birth year, and sequence number.

    Args:
        db: Database session
        student_id: Student ID
        group_id: Group ID

    Returns:
        Tuple of (contract_number, birth_year, sequence_number)
        Example: ("N12020", 2020, 1)

    Raises:
        ContractNumberAllocationError: If allocation fails
    """
    # Get student to determine birth year
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()

    if not student:
        raise ContractNumberAllocationError(f"Student with ID {student_id} not found")

    birth_year = student.date_of_birth.year

    # Get available numbers
    available_numbers = await get_available_contract_numbers(db, group_id, birth_year)

    if not available_numbers:
        raise ContractNumberAllocationError(
            f"No available contract numbers for group {group_id} and birth year {birth_year}. "
            f"Group may be at full capacity for this birth year."
        )

    # Use the first available number
    sequence_number = available_numbers[0]
    contract_number = f"N{sequence_number}{birth_year}"

    return contract_number, birth_year, sequence_number


async def is_group_full(
    db: AsyncSession,
    group_id: int,
    birth_year: Optional[int] = None,
    archive_year: Optional[int] = None
) -> bool:
    """
    Check if a group is full.

    Args:
        db: Database session
        group_id: Group ID
        birth_year: Optional birth year to check capacity for specific year
        archive_year: Archive year filter (defaults to current year)

    Returns:
        True if group is full, False otherwise
    """
    from datetime import datetime
    if archive_year is None:
        archive_year = datetime.now().year

    # Get group capacity
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group = group_result.scalar_one_or_none()

    if not group:
        return True  # Treat non-existent group as full

    if birth_year:
        # Check capacity for specific birth year
        available = await get_available_contract_numbers(db, group_id, birth_year, archive_year)
        return len(available) == 0
    else:
        # Check overall capacity across all birth years for the archive year
        contracts_result = await db.execute(
            select(Contract).where(
                and_(
                    Contract.group_id == group_id,
                    Contract.archive_year == archive_year,
                    or_(
                        Contract.status == ContractStatus.ACTIVE,
                        Contract.status == ContractStatus.EXPIRED
                    )
                )
            )
        )
        active_contracts = contracts_result.scalars().all()

        return len(active_contracts) >= group.capacity


async def get_next_available_sequence(
    db: AsyncSession,
    group_id: int,
    birth_year: int
) -> Optional[int]:
    """
    Get the next available sequence number for a birth year in a group.

    Returns None if no sequences are available.
    """
    available = await get_available_contract_numbers(db, group_id, birth_year)
    return available[0] if available else None


async def free_contract_number(
    db: AsyncSession,
    contract_id: int
) -> bool:
    """
    Free a contract number by marking the contract as terminated.

    This makes the contract number available for reuse.

    Args:
        db: Database session
        contract_id: Contract ID to free

    Returns:
        True if successful, False otherwise
    """
    contract_result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return False

    # Contract numbers are freed when status is TERMINATED
    # The contract itself remains in DB for history, but the number becomes available
    contract.status = ContractStatus.TERMINATED

    await db.commit()
    return True
