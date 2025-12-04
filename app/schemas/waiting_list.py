from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.student import StudentRead
from app.schemas.group import GroupRead


class WaitingListCreate(BaseModel):
    """Add student to waiting list"""
    student_id: int
    group_id: int
    priority: int = Field(default=0, ge=0, le=100, description="Priority in queue (higher = earlier)")
    notes: Optional[str] = None


class WaitingListUpdate(BaseModel):
    """Update waiting list entry"""
    priority: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None


class WaitingListRead(BaseModel):
    """Waiting list entry with student and group info"""
    id: int
    student_id: int
    group_id: int
    priority: int
    notes: Optional[str] = None
    added_by_user_id: Optional[int] = None
    created_at: datetime
    student: StudentRead
    group: GroupRead

    class Config:
        from_attributes = True


class WaitingListSimple(BaseModel):
    """Simplified waiting list entry"""
    id: int
    student_id: int
    group_id: int
    priority: int
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
