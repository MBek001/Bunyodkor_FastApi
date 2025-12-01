from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.models.enums import AttendanceStatus


class SessionRead(BaseModel):
    id: int
    session_date: date
    topic: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    group_id: int
    created_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    session_date: date
    topic: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    group_id: int


class SessionWithAttendances(SessionRead):
    """Session with attendance records"""
    attendances: list["AttendanceRead"] = []


class AttendanceRead(BaseModel):
    id: int
    status: AttendanceStatus
    comment: Optional[str] = None
    session_id: int
    student_id: int
    marked_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AttendanceCreate(BaseModel):
    student_id: int
    status: AttendanceStatus
    comment: Optional[str] = None


class BulkAttendanceCreate(BaseModel):
    """Create multiple attendance records for a session"""
    session_id: int
    attendances: list[AttendanceCreate]


class AttendanceStats(BaseModel):
    """Attendance statistics for a student or group"""
    total_sessions: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_rate: float  # Percentage of present sessions


class StudentWithDebtInfo(BaseModel):
    student_id: int
    first_name: str
    last_name: str
    has_debt: bool
    debt_amount: float
    debt_warning: Optional[str] = None


class GateLogRead(BaseModel):
    id: int
    allowed: bool
    reason: Optional[str] = None
    gate_timestamp: datetime
    student_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GateCallbackRequest(BaseModel):
    student_id: Optional[int] = None
    face_id: Optional[str] = None


class GateCallbackResponse(BaseModel):
    allowed: bool
    reason: str
    student_id: Optional[int] = None
