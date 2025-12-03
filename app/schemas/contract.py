from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.models.enums import ContractStatus


class ContractRead(BaseModel):
    id: int
    contract_number: str
    start_date: date
    end_date: date
    monthly_fee: float
    status: ContractStatus
    student_id: int
    terminated_at: Optional[datetime] = None
    terminated_by_user_id: Optional[int] = None
    termination_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ContractCreate(BaseModel):
    contract_number: str
    start_date: date
    end_date: date
    monthly_fee: float
    status: ContractStatus = ContractStatus.ACTIVE
    student_id: int


class ContractUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    monthly_fee: Optional[float] = None
    status: Optional[ContractStatus] = None


class ContractTerminate(BaseModel):
    termination_reason: str
    terminated_at: Optional[datetime] = None  # If not provided, will use current datetime
