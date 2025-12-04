from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.db import get_db
from app.core.permissions import PERM_CONTRACTS_EDIT, PERM_CONTRACTS_VIEW
from app.models.domain import WaitingList, Student, Group
from app.schemas.waiting_list import WaitingListCreate, WaitingListUpdate, WaitingListRead
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission, CurrentUser

router = APIRouter(prefix="/waiting-list", tags=["Waiting List"])


@router.get("", response_model=DataResponse[list[WaitingListRead]], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_waiting_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    group_id: Optional[int] = None,
    student_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get waiting list entries.

    Filter by group_id to see all students waiting for a specific group.
    Filter by student_id to see which groups a student is waiting for.

    Results are ordered by priority (high to low), then by created_at (oldest first).
    """
    query = (
        select(WaitingList)
        .options(
            selectinload(WaitingList.student),
            selectinload(WaitingList.group)
        )
        .order_by(WaitingList.priority.desc(), WaitingList.created_at)
    )

    if group_id:
        query = query.where(WaitingList.group_id == group_id)
    if student_id:
        query = query.where(WaitingList.student_id == student_id)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    waiting_list = result.scalars().all()

    # Count total
    count_query = select(func.count(WaitingList.id))
    if group_id:
        count_query = count_query.where(WaitingList.group_id == group_id)
    if student_id:
        count_query = count_query.where(WaitingList.student_id == student_id)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return DataResponse(
        data=[WaitingListRead.model_validate(w) for w in waiting_list],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.post("", response_model=DataResponse[WaitingListRead], dependencies=[Depends(require_permission(PERM_CONTRACTS_EDIT))])
async def add_to_waiting_list(
    data: WaitingListCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Add a student to waiting list for a group.

    Used when a group is full and student needs to wait for a slot.
    """
    # Check if student exists
    student_result = await db.execute(select(Student).where(Student.id == data.student_id))
    if not student_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Student with ID {data.student_id} not found")

    # Check if group exists
    group_result = await db.execute(select(Group).where(Group.id == data.group_id))
    if not group_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Group with ID {data.group_id} not found")

    # Check if already in waiting list for this group
    existing = await db.execute(
        select(WaitingList).where(
            WaitingList.student_id == data.student_id,
            WaitingList.group_id == data.group_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="This student is already in the waiting list for this group"
        )

    waiting_entry = WaitingList(
        student_id=data.student_id,
        group_id=data.group_id,
        priority=data.priority,
        notes=data.notes,
        added_by_user_id=user.id
    )

    db.add(waiting_entry)
    await db.commit()

    # Refresh with relationships
    await db.refresh(waiting_entry)
    result = await db.execute(
        select(WaitingList)
        .options(
            selectinload(WaitingList.student),
            selectinload(WaitingList.group)
        )
        .where(WaitingList.id == waiting_entry.id)
    )
    waiting_entry = result.scalar_one()

    return DataResponse(data=WaitingListRead.model_validate(waiting_entry))


@router.get("/{waiting_id}", response_model=DataResponse[WaitingListRead], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_waiting_list_entry(
    waiting_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific waiting list entry by ID."""
    result = await db.execute(
        select(WaitingList)
        .options(
            selectinload(WaitingList.student),
            selectinload(WaitingList.group)
        )
        .where(WaitingList.id == waiting_id)
    )
    waiting_entry = result.scalar_one_or_none()

    if not waiting_entry:
        raise HTTPException(status_code=404, detail="Waiting list entry not found")

    return DataResponse(data=WaitingListRead.model_validate(waiting_entry))


@router.patch("/{waiting_id}", response_model=DataResponse[WaitingListRead], dependencies=[Depends(require_permission(PERM_CONTRACTS_EDIT))])
async def update_waiting_list_entry(
    waiting_id: int,
    data: WaitingListUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Update a waiting list entry.

    Can update priority or notes.
    """
    result = await db.execute(select(WaitingList).where(WaitingList.id == waiting_id))
    waiting_entry = result.scalar_one_or_none()

    if not waiting_entry:
        raise HTTPException(status_code=404, detail="Waiting list entry not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(waiting_entry, field, value)

    await db.commit()

    # Refresh with relationships
    result = await db.execute(
        select(WaitingList)
        .options(
            selectinload(WaitingList.student),
            selectinload(WaitingList.group)
        )
        .where(WaitingList.id == waiting_id)
    )
    waiting_entry = result.scalar_one()

    return DataResponse(data=WaitingListRead.model_validate(waiting_entry))


@router.delete("/{waiting_id}", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_CONTRACTS_EDIT))])
async def remove_from_waiting_list(
    waiting_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Remove a student from waiting list.

    Use this when:
    - Student gets a contract slot
    - Student no longer wants to join this group
    - Entry is no longer valid
    """
    result = await db.execute(select(WaitingList).where(WaitingList.id == waiting_id))
    waiting_entry = result.scalar_one_or_none()

    if not waiting_entry:
        raise HTTPException(status_code=404, detail="Waiting list entry not found")

    await db.delete(waiting_entry)
    await db.commit()

    return DataResponse(data={"message": "Student removed from waiting list successfully"})


@router.get("/group/{group_id}/next", response_model=DataResponse[WaitingListRead | None], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_next_in_queue(
    group_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get the next student in queue for a group.

    Returns the waiting list entry with highest priority, or oldest if priorities are equal.
    Returns null if no one is waiting.

    Useful when a contract is canceled and you want to know who should get the slot.
    """
    result = await db.execute(
        select(WaitingList)
        .options(
            selectinload(WaitingList.student),
            selectinload(WaitingList.group)
        )
        .where(WaitingList.group_id == group_id)
        .order_by(WaitingList.priority.desc(), WaitingList.created_at)
        .limit(1)
    )
    next_entry = result.scalar_one_or_none()

    if not next_entry:
        return DataResponse(data=None)

    return DataResponse(data=WaitingListRead.model_validate(next_entry))
