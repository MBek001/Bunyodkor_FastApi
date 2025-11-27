from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.core.db import get_db
from app.core.permissions import PERM_STUDENTS_VIEW, PERM_STUDENTS_EDIT
from app.models.domain import Student
from app.models.finance import Transaction
from app.models.attendance import Attendance, GateLog
from app.schemas.student import StudentRead, StudentCreate, StudentUpdate
from app.schemas.contract import ContractRead
from app.schemas.transaction import TransactionRead
from app.schemas.attendance import AttendanceRead, GateLogRead
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", response_model=DataResponse[list[StudentRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Student)

    if search:
        query = query.where(
            or_(
                Student.first_name.ilike(f"%{search}%"),
                Student.last_name.ilike(f"%{search}%"),
            )
        )
    if group_id:
        query = query.where(Student.group_id == group_id)
    if status:
        query = query.where(Student.status == status)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    students = result.scalars().all()

    count_query = select(func.count(Student.id))
    if search:
        count_query = count_query.where(
            or_(
                Student.first_name.ilike(f"%{search}%"),
                Student.last_name.ilike(f"%{search}%"),
            )
        )
    if group_id:
        count_query = count_query.where(Student.group_id == group_id)
    if status:
        count_query = count_query.where(Student.status == status)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return DataResponse(
        data=[StudentRead.model_validate(s) for s in students],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.post("", response_model=DataResponse[StudentRead], dependencies=[Depends(require_permission(PERM_STUDENTS_EDIT))])
async def create_student(
    data: StudentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    student = Student(**data.model_dump())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return DataResponse(data=StudentRead.model_validate(student))


@router.get("/{student_id}", response_model=DataResponse[StudentRead], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return DataResponse(data=StudentRead.model_validate(student))


@router.patch("/{student_id}", response_model=DataResponse[StudentRead], dependencies=[Depends(require_permission(PERM_STUDENTS_EDIT))])
async def update_student(
    student_id: int,
    data: StudentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field, value)

    await db.commit()
    await db.refresh(student)
    return DataResponse(data=StudentRead.model_validate(student))


@router.get("/{student_id}/contracts", response_model=DataResponse[list[ContractRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_contracts(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.domain import Contract
    result = await db.execute(select(Contract).where(Contract.student_id == student_id))
    contracts = result.scalars().all()
    return DataResponse(data=[ContractRead.model_validate(c) for c in contracts])


@router.get("/{student_id}/transactions", response_model=DataResponse[list[TransactionRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_transactions(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Transaction).where(Transaction.student_id == student_id))
    transactions = result.scalars().all()
    return DataResponse(data=[TransactionRead.model_validate(t) for t in transactions])


@router.get("/{student_id}/attendance", response_model=DataResponse[list[AttendanceRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_attendance(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Attendance).where(Attendance.student_id == student_id))
    attendance = result.scalars().all()
    return DataResponse(data=[AttendanceRead.model_validate(a) for a in attendance])


@router.get("/{student_id}/gatelogs", response_model=DataResponse[list[GateLogRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_gatelogs(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(GateLog).where(GateLog.student_id == student_id))
    logs = result.scalars().all()
    return DataResponse(data=[GateLogRead.model_validate(l) for l in logs])
