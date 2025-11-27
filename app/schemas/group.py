from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class GroupRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    schedule_days: Optional[str] = None
    schedule_time: Optional[str] = None
    coach_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    schedule_days: Optional[str] = None
    schedule_time: Optional[str] = None
    coach_id: Optional[int] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schedule_days: Optional[str] = None
    schedule_time: Optional[str] = None
    coach_id: Optional[int] = None
