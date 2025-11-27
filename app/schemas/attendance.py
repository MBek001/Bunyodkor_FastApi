from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.models.enums import AttendanceStatus


class SessionRead(BaseModel):
    id: int
    session_date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    group_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    session_date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    group_id: int


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
