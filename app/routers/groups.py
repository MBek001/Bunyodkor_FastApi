from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.db import get_db
from app.core.permissions import PERM_GROUPS_VIEW, PERM_GROUPS_EDIT
from app.models.domain import Group, Student
from app.schemas.group import GroupRead, GroupCreate, GroupUpdate
from app.schemas.student import StudentRead
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get("", response_model=DataResponse[list[GroupRead]], dependencies=[Depends(require_permission(PERM_GROUPS_VIEW))])
async def get_groups(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    result = await db.execute(select(Group).offset(offset).limit(page_size))
    groups = result.scalars().all()

    count_result = await db.execute(select(func.count(Group.id)))
    total = count_result.scalar()

    return DataResponse(
        data=[GroupRead.model_validate(g) for g in groups],
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
    if data.coach_id:
        from app.models.auth import User
        coach_result = await db.execute(select(User).where(User.id == data.coach_id))
        if not coach_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Coach with ID {data.coach_id} not found")

    group = Group(**data.model_dump())
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
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    update_data = data.model_dump(exclude_unset=True)

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
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db.delete(group)
    await db.commit()

    return DataResponse(data={"message": "Group deleted successfully"})
