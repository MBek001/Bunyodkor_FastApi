from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from collections import defaultdict
from app.core.db import get_db
from app.core.permissions import PERM_GROUPS_VIEW, PERM_GROUPS_EDIT
from app.models.domain import Group, Student, Contract, WaitingList
from app.schemas.group import GroupRead, GroupCreate, GroupUpdate, GroupCapacityInfo, GroupCapacityByYear
from app.schemas.student import StudentRead
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission
from app.models.enums import ContractStatus, GroupStatus

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get("", response_model=DataResponse[list[GroupRead]], dependencies=[Depends(require_permission(PERM_GROUPS_VIEW))])
async def get_groups(
    db: Annotated[AsyncSession, Depends(get_db)],
    archive_year: int | None = Query(None, description="Filter by archive year (NULL for groups not yet archived)"),
    status: GroupStatus | None = Query(None, description="Filter by status (ACTIVE, ARCHIVED, DELETED)"),
    include_archived: bool = Query(False, description="Include archived groups (ignored if status is specified)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get all groups with optional filters.

    Default behavior (no filters):
    - Shows all ACTIVE groups regardless of archive_year

    Filters:
    - archive_year: Filter by specific year, or use NULL to find groups not yet archived
    - status: Filter by specific status (overrides include_archived)
    - include_archived: Include all statuses if True (ignored if status is specified)
    """
    query = select(Group)

    # Filter by archive_year if specified
    if archive_year is not None:
        query = query.where(Group.archive_year == archive_year)

    # Filter by status if specified (takes priority)
    if status is not None:
        query = query.where(Group.status == status)
    # Otherwise, default to ACTIVE only unless include_archived is True
    elif not include_archived:
        query = query.where(Group.status == GroupStatus.ACTIVE)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    groups = result.scalars().all()

    count_query = select(func.count(Group.id))
    if archive_year is not None:
        count_query = count_query.where(Group.archive_year == archive_year)
    if status is not None:
        count_query = count_query.where(Group.status == status)
    elif not include_archived:
        count_query = count_query.where(Group.status == GroupStatus.ACTIVE)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Enrich groups with student counts and waiting list counts
    from app.models.enums import StudentStatus
    groups_data = []
    for group in groups:
        group_dict = GroupRead.model_validate(group).model_dump()

        # Count active students in this group
        student_count_result = await db.execute(
            select(func.count(Student.id)).where(
                and_(
                    Student.group_id == group.id,
                    Student.status == StudentStatus.ACTIVE
                )
            )
        )
        group_dict['active_students_count'] = student_count_result.scalar() or 0

        # Count waiting list entries
        waiting_count_result = await db.execute(
            select(func.count(WaitingList.id)).where(WaitingList.group_id == group.id)
        )
        group_dict['waiting_list_count'] = waiting_count_result.scalar() or 0

        groups_data.append(group_dict)

    return DataResponse(
        data=groups_data,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.post("", response_model=DataResponse[GroupRead], dependencies=[Depends(require_permission(PERM_GROUPS_EDIT))])
async def create_group(
    data: GroupCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a new group with current year as archive year.

    Identifier must be unique (enforced by database constraint).
    Multiple groups can have the same birth year as long as identifiers are different.
    """
    # Check if identifier already exists (excluding DELETED groups)
    existing_identifier = await db.execute(
        select(Group).where(
            Group.identifier == data.identifier,
            Group.status != GroupStatus.DELETED
        )
    )
    if existing_identifier.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Identifier '{data.identifier}' already exists. Please use a unique identifier."
        )

    if data.coach_id:
        from app.models.auth import User
        coach_result = await db.execute(select(User).where(User.id == data.coach_id))
        if not coach_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Coach with ID {data.coach_id} not found")

    group_data = data.model_dump()
    # Don't auto-set archive_year - it should be NULL until actually archived
    group = Group(**group_data)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return DataResponse(data=GroupRead.model_validate(group))


@router.get("/{group_id}", response_model=DataResponse[GroupRead], dependencies=[Depends(require_permission(PERM_GROUPS_VIEW))])
async def get_group(
    group_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return DataResponse(data=GroupRead.model_validate(group))


@router.patch("/{group_id}", response_model=DataResponse[GroupRead], dependencies=[Depends(require_permission(PERM_GROUPS_EDIT))])
async def update_group(
    group_id: int,
    data: GroupUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Update group details.

    Identifier must remain unique (enforced by database constraint).
    Multiple groups can have the same birth year as long as identifiers are different.
    """
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    update_data = data.model_dump(exclude_unset=True)

    # Check if identifier is being changed and if it already exists (excluding DELETED groups)
    if "identifier" in update_data and update_data["identifier"] != group.identifier:
        existing_identifier = await db.execute(
            select(Group).where(
                Group.identifier == update_data["identifier"],
                Group.status != GroupStatus.DELETED
            )
        )
        if existing_identifier.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Identifier '{update_data['identifier']}' already exists. Please use a unique identifier."
            )

    if "coach_id" in update_data and update_data["coach_id"] is not None:
        from app.models.auth import User
        coach_result = await db.execute(select(User).where(User.id == update_data["coach_id"]))
        if not coach_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Coach with ID {update_data['coach_id']} not found")

    for field, value in update_data.items():
        setattr(group, field, value)

    await db.commit()
    await db.refresh(group)
    return DataResponse(data=GroupRead.model_validate(group))


@router.get("/{group_id}/students", response_model=DataResponse[list[StudentRead]], dependencies=[Depends(require_permission(PERM_GROUPS_VIEW))])
async def get_group_students(
    group_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Student).where(Student.group_id == group_id))
    students = result.scalars().all()
    return DataResponse(data=[StudentRead.model_validate(s) for s in students])


@router.delete("/{group_id}", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_GROUPS_EDIT))])
async def delete_group(
    group_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Soft delete a group by setting its status to DELETED.
    The group is not actually removed from the database.
    """
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Soft delete: set status to DELETED instead of actually deleting
    group.status = GroupStatus.DELETED
    await db.commit()

    return DataResponse(data={"message": "Group deleted successfully"})


@router.post("/bulk-delete", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_GROUPS_EDIT))])
async def bulk_delete_groups(
    group_ids: list[int],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Soft delete multiple groups by setting their status to DELETED.
    Groups are not actually removed from the database.
    """
    if not group_ids:
        raise HTTPException(status_code=400, detail="No group IDs provided")

    deleted_count = 0
    errors = []

    for group_id in group_ids:
        try:
            result = await db.execute(select(Group).where(Group.id == group_id))
            group = result.scalar_one_or_none()

            if not group:
                errors.append({"group_id": group_id, "error": "Group not found"})
                continue

            # Soft delete: set status to DELETED instead of actually deleting
            group.status = GroupStatus.DELETED
            deleted_count += 1
        except Exception as e:
            errors.append({"group_id": group_id, "error": str(e)})

    await db.commit()

    return DataResponse(data={
        "message": f"Deleted {deleted_count} group(s)",
        "deleted_count": deleted_count,
        "total_requested": len(group_ids),
        "errors": errors if errors else None
    })


@router.get("/{group_id}/capacity", response_model=DataResponse[GroupCapacityInfo], dependencies=[Depends(require_permission(PERM_GROUPS_VIEW))])
async def get_group_capacity(
    group_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    archive_year: int | None = Query(None, description="Filter by archive year (defaults to current year)"),
):
    """
    Get detailed capacity information for a group.

    Returns:
    - Group capacity and current usage
    - Breakdown by birth year (how many students from each birth year)
    - Available slots
    - Waiting list count

    Useful for:
    - Checking if group has space for new students
    - Seeing distribution of students by birth year
    - Managing group capacity
    """
    from datetime import datetime
    if archive_year is None:
        archive_year = datetime.now().year

    # Get group
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group = group_result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Get active and expired contracts for this group (not terminated) for the archive year
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
    contracts = contracts_result.scalars().all()

    # Count active contracts
    active_contracts_count = sum(1 for c in contracts if c.status == ContractStatus.ACTIVE)

    # Group contracts by birth year
    by_year = defaultdict(lambda: {"used": 0, "available": 0})

    for contract in contracts:
        by_year[contract.birth_year]["used"] += 1

    # Calculate available slots for each year
    for year_str in by_year:
        by_year[year_str]["available"] = group.capacity - by_year[year_str]["used"]

    # Get waiting list count
    waiting_result = await db.execute(
        select(func.count(WaitingList.id)).where(WaitingList.group_id == group_id)
    )
    waiting_count = waiting_result.scalar() or 0

    # Convert by_year to the schema format
    by_year_dict = {
        str(year): GroupCapacityByYear(used=data["used"], available=data["available"])
        for year, data in by_year.items()
    }

    return DataResponse(data=GroupCapacityInfo(
        group_id=group_id,
        group_name=group.name,
        capacity=group.capacity,
        active_contracts=active_contracts_count,
        available_slots=group.capacity - active_contracts_count,
        waiting_list_count=waiting_count,
        by_birth_year=by_year_dict
    ))
