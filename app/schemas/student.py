from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.models.enums import StudentStatus


class StudentRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    date_of_birth: date
    phone: Optional[str] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    face_id: Optional[str] = None
    status: StudentStatus
    group_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    phone: Optional[str] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    face_id: Optional[str] = None
    status: StudentStatus = StudentStatus.ACTIVE
    group_id: Optional[int] = None


class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    face_id: Optional[str] = None
    status: Optional[StudentStatus] = None
    group_id: Optional[int] = None


class ParentRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    relationship_type: Optional[str] = None
    student_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ParentCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: Optional[str] = None
    relationship_type: Optional[str] = None
    student_id: int


class ParentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    relationship_type: Optional[str] = None


class StudentDebtInfo(BaseModel):
    student: StudentRead
    total_expected: float
    total_paid: float
    debt_amount: float
    active_contracts_count: int

    class Config:
        from_attributes = True
