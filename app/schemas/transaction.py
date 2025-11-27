from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.enums import PaymentStatus, PaymentSource


class TransactionRead(BaseModel):
    id: int
    external_id: Optional[str] = None
    amount: float
    source: PaymentSource
    status: PaymentStatus
    paid_at: Optional[datetime] = None
    comment: Optional[str] = None
    student_id: Optional[int] = None
    contract_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    external_id: Optional[str] = None
    amount: float
    source: PaymentSource
    status: PaymentStatus = PaymentStatus.PENDING
    paid_at: Optional[datetime] = None
    comment: Optional[str] = None
    student_id: Optional[int] = None
    contract_id: Optional[int] = None


class TransactionUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    comment: Optional[str] = None


class TransactionAssign(BaseModel):
    student_id: int
    contract_id: int


class ManualTransactionCreate(BaseModel):
    amount: float
    source: PaymentSource
    student_id: int
    contract_id: int
    comment: Optional[str] = None
    paid_at: Optional[datetime] = None
