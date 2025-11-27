from typing import Annotated, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.core.db import get_db
from app.core.permissions import PERM_ATTENDANCE_COACH_MARK
from app.models.domain import Group, Student
from app.models.attendance import Session, Attendance
from app.schemas.group import GroupRead
from app.schemas.attendance import SessionRead, AttendanceCreate, StudentWithDebtInfo
from app.schemas.common import DataResponse
from app.deps import require_permission, CurrentUser
from app.services.debt import calculate_student_debt

router = APIRouter(prefix="/coach", tags=["Coach"])


@router.get("/groups", response_model=DataResponse[list[GroupRead]], dependencies=[Depends(require_permission(PERM_ATTENDANCE_COACH_MARK))])
async def get_coach_groups(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Group).where(Group.coach_id == user.id))
    groups = result.scalars().all()
    return DataResponse(data=[GroupRead.model_validate(g) for g in groups])


@router.get("/sessions", response_model=DataResponse[list[SessionRead]], dependencies=[Depends(require_permission(PERM_ATTENDANCE_COACH_MARK))])
async def get_coach_sessions(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    date_filter: Optional[date] = Query(None, alias="date"),
):
    session_date = date_filter or date.today()

    result = await db.execute(
        select(Session)
        .join(Group)
        .where(and_(Group.coach_id == user.id, Session.session_date == session_date))
    )
    sessions = result.scalars().all()
    return DataResponse(data=[SessionRead.model_validate(s) for s in sessions])


@router.get("/sessions/{session_id}/students-with-debt-info", response_model=DataResponse[list[StudentWithDebtInfo]], dependencies=[Depends(require_permission(PERM_ATTENDANCE_COACH_MARK))])
async def get_session_students_with_debt(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session_result = await db.execute(select(Session).where(Session.id == session_id))
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    students_result = await db.execute(select(Student).where(Student.group_id == session.group_id))
    students = students_result.scalars().all()

    students_with_debt = []
    for student in students:
        debt = await calculate_student_debt(db, student.id)
        has_debt = debt > 0

        students_with_debt.append(
            StudentWithDebtInfo(
                student_id=student.id,
                first_name=student.first_name,
                last_name=student.last_name,
                has_debt=has_debt,
                debt_amount=debt,
                debt_warning=f"Student owes {debt} UZS" if has_debt else None,
            )
        )

    return DataResponse(data=students_with_debt)


@router.post("/sessions/{session_id}/attendance", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_ATTENDANCE_COACH_MARK))])
async def mark_attendance(
    session_id: int,
    data: AttendanceCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session_result = await db.execute(select(Session).where(Session.id == session_id))
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    student_result = await db.execute(select(Student).where(Student.id == data.student_id))
    if not student_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Student with ID {data.student_id} not found")

    attendance = Attendance(
        session_id=session_id,
        student_id=data.student_id,
        status=data.status,
        comment=data.comment,
        marked_by_user_id=user.id,
    )
    db.add(attendance)
    await db.commit()
    await db.refresh(attendance)

    return DataResponse(data={"message": "Attendance marked successfully", "attendance_id": attendance.id})
