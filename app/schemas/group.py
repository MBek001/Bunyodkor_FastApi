from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field


class GroupRead(BaseModel):
    id: int
    name: str
    birth_year: int
    description: Optional[str] = None
    schedule_days: Optional[str] = None
    schedule_time: Optional[str] = None
    capacity: int = 100
    coach_id: Optional[int] = None
    created_at: datetime

    # Optional stats - populated when requested
    active_students_count: Optional[int] = Field(default=None, description="Number of active students in this group")
    waiting_list_count: Optional[int] = Field(default=None, description="Number of students waiting to join this group")

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    name: str
    birth_year: int = Field(description="Birth year of students in this group (e.g., 2010, 2015, 2020)")
    description: Optional[str] = None
    schedule_days: Optional[str] = None
    schedule_time: Optional[str] = None
    capacity: int = Field(default=100, ge=1, le=500, description="Maximum number of students in group")
    coach_id: Optional[int] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    birth_year: Optional[int] = None
    description: Optional[str] = None
    schedule_days: Optional[str] = None
    schedule_time: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=1, le=500)
    coach_id: Optional[int] = None


class GroupCapacityByYear(BaseModel):
    """Capacity info for a specific birth year"""
    used: int
    available: int


class GroupCapacityInfo(BaseModel):
    """Detailed capacity information for a group"""
    group_id: int
    group_name: str
    capacity: int
    active_contracts: int
    available_slots: int
    waiting_list_count: int
    by_birth_year: Dict[str, GroupCapacityByYear]
