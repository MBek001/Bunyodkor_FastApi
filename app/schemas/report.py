from datetime import date
from typing import Optional
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    today_revenue: float
    active_students: int
    total_debtors: int
    today_sessions: int


class FinanceReportItem(BaseModel):
    source: str
    total_amount: float
    transaction_count: int


class FinanceReport(BaseModel):
    from_date: date
    to_date: date
    total_revenue: float
    breakdown: list[FinanceReportItem]


class GroupAttendanceReport(BaseModel):
    group_id: int
    group_name: str
    total_sessions: int
    total_students: int
    attendance_percentage: float


class StudentAttendanceReport(BaseModel):
    student_id: int
    student_name: str
    total_sessions: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_percentage: float


class CoachAttendanceReport(BaseModel):
    coach_id: int
    coach_name: str
    groups: list[GroupAttendanceReport]


class DebtorItem(BaseModel):
    student_id: int
    student_name: str
    contract_number: str
    debt_amount: float
    group_name: Optional[str] = None
