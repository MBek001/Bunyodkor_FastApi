from typing import Annotated, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.core.db import get_db
from app.core.permissions import PERM_REPORTS_DASHBOARD_VIEW, PERM_REPORTS_FINANCE_VIEW, PERM_REPORTS_ATTENDANCE_VIEW
from app.models.domain import Student, Group
from app.models.finance import Transaction
from app.models.attendance import Session, Attendance
from app.models.enums import StudentStatus, PaymentStatus, AttendanceStatus
from app.schemas.report import (
    DashboardSummary,
    FinanceReport,
    FinanceReportItem,
    GroupAttendanceReport,
    StudentAttendanceReport,
    DebtorItem,
)
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission
from app.services.debt import calculate_student_debt

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dashboard/summary", response_model=DataResponse[DashboardSummary], dependencies=[Depends(require_permission(PERM_REPORTS_DASHBOARD_VIEW))])
async def get_dashboard_summary(db: Annotated[AsyncSession, Depends(get_db)]):
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    today_revenue_result = await db.execute(
        select(func.sum(Transaction.amount))
        .where(and_(Transaction.status == PaymentStatus.SUCCESS, Transaction.paid_at >= today_start))
    )
    today_revenue = today_revenue_result.scalar() or 0.0

    active_students_result = await db.execute(
        select(func.count(Student.id)).where(Student.status == StudentStatus.ACTIVE)
    )
    active_students = active_students_result.scalar() or 0

    today_sessions_result = await db.execute(
        select(func.count(Session.id)).where(Session.session_date == today)
    )
    today_sessions = today_sessions_result.scalar() or 0

    return DataResponse(
        data=DashboardSummary(
            today_revenue=float(today_revenue),
            active_students=active_students,
            total_debtors=0,
            today_sessions=today_sessions,
        )
    )


@router.get("/finance", response_model=DataResponse[FinanceReport], dependencies=[Depends(require_permission(PERM_REPORTS_FINANCE_VIEW))])
async def get_finance_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date = Query(...),
    to_date: date = Query(...),
):
    from_datetime = datetime.combine(from_date, datetime.min.time())
    to_datetime = datetime.combine(to_date, datetime.max.time())

    result = await db.execute(
        select(Transaction.source, func.sum(Transaction.amount), func.count(Transaction.id))
        .where(
            and_(
                Transaction.status == PaymentStatus.SUCCESS,
                Transaction.paid_at >= from_datetime,
                Transaction.paid_at <= to_datetime,
            )
        )
        .group_by(Transaction.source)
    )
    breakdown_data = result.all()

    breakdown = [
        FinanceReportItem(source=str(source), total_amount=float(total), transaction_count=count)
        for source, total, count in breakdown_data
    ]

    total_revenue = sum(item.total_amount for item in breakdown)

    return DataResponse(
        data=FinanceReport(
            from_date=from_date,
            to_date=to_date,
            total_revenue=total_revenue,
            breakdown=breakdown,
        )
    )


@router.get("/attendance/groups", response_model=DataResponse[list[GroupAttendanceReport]], dependencies=[Depends(require_permission(PERM_REPORTS_ATTENDANCE_VIEW))])
async def get_group_attendance_report(db: Annotated[AsyncSession, Depends(get_db)]):
    groups_result = await db.execute(select(Group))
    groups = groups_result.scalars().all()

    reports = []
    for group in groups:
        sessions_result = await db.execute(select(func.count(Session.id)).where(Session.group_id == group.id))
        total_sessions = sessions_result.scalar() or 0

        students_result = await db.execute(select(func.count(Student.id)).where(Student.group_id == group.id))
        total_students = students_result.scalar() or 0

        present_result = await db.execute(
            select(func.count(Attendance.id))
            .join(Session)
            .where(and_(Session.group_id == group.id, Attendance.status == AttendanceStatus.PRESENT))
        )
        present_count = present_result.scalar() or 0

        total_possible = total_sessions * total_students
        attendance_percentage = (present_count / total_possible * 100) if total_possible > 0 else 0.0

        reports.append(
            GroupAttendanceReport(
                group_id=group.id,
                group_name=group.name,
                total_sessions=total_sessions,
                total_students=total_students,
                attendance_percentage=attendance_percentage,
            )
        )

    return DataResponse(data=reports)


@router.get("/attendance/students/{student_id}", response_model=DataResponse[StudentAttendanceReport], dependencies=[Depends(require_permission(PERM_REPORTS_ATTENDANCE_VIEW))])
async def get_student_attendance_report(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()

    if not student:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Student not found")

    total_sessions_result = await db.execute(
        select(func.count(Session.id)).where(Session.group_id == student.group_id)
    )
    total_sessions = total_sessions_result.scalar() or 0

    present_result = await db.execute(
        select(func.count(Attendance.id))
        .where(and_(Attendance.student_id == student_id, Attendance.status == AttendanceStatus.PRESENT))
    )
    present_count = present_result.scalar() or 0

    absent_result = await db.execute(
        select(func.count(Attendance.id))
        .where(and_(Attendance.student_id == student_id, Attendance.status == AttendanceStatus.ABSENT))
    )
    absent_count = absent_result.scalar() or 0

    late_result = await db.execute(
        select(func.count(Attendance.id))
        .where(and_(Attendance.student_id == student_id, Attendance.status == AttendanceStatus.LATE))
    )
    late_count = late_result.scalar() or 0

    attendance_percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0.0

    return DataResponse(
        data=StudentAttendanceReport(
            student_id=student.id,
            student_name=f"{student.first_name} {student.last_name}",
            total_sessions=total_sessions,
            present_count=present_count,
            absent_count=absent_count,
            late_count=late_count,
            attendance_percentage=attendance_percentage,
        )
    )


@router.get("/debtors", response_model=DataResponse[list[DebtorItem]], dependencies=[Depends(require_permission(PERM_REPORTS_FINANCE_VIEW))])
async def get_debtors_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    group_id: Optional[int] = None,
    min_debt_amount: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Student)

    if group_id:
        query = query.where(Student.group_id == group_id)

    result = await db.execute(query)
    students = result.scalars().all()

    debtors = []
    for student in students:
        debt = await calculate_student_debt(db, student.id)

        if debt > 0 and (min_debt_amount is None or debt >= min_debt_amount):
            from app.models.domain import Contract
            contract_result = await db.execute(
                select(Contract).where(Contract.student_id == student.id).order_by(Contract.created_at.desc())
            )
            contract = contract_result.scalar_one_or_none()

            group_name = None
            if student.group_id:
                group_result = await db.execute(select(Group).where(Group.id == student.group_id))
                group = group_result.scalar_one_or_none()
                if group:
                    group_name = group.name

            debtors.append(
                DebtorItem(
                    student_id=student.id,
                    student_name=f"{student.first_name} {student.last_name}",
                    contract_number=contract.contract_number if contract else "N/A",
                    debt_amount=debt,
                    group_name=group_name,
                )
            )

    offset = (page - 1) * page_size
    paginated_debtors = debtors[offset : offset + page_size]

    return DataResponse(
        data=paginated_debtors,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=len(debtors),
            total_pages=(len(debtors) + page_size - 1) // page_size,
        ),
    )
