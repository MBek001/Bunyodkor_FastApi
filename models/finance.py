from enum import Enum
from sqlalchemy import (
    Column, Integer, String, ForeignKey,
    DateTime, Numeric, Enum as SAEnum, JSON, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base, TimestampMixin


class TransactionSource(str, Enum):
    PAYME = "PAYME"
    CLICK = "CLICK"
    BANK = "BANK"
    MANUAL = "MANUAL"


class TransactionStatus(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    CANCELLED = "CANCELLED"
    REFUND = "REFUND"


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(100), nullable=True, index=True)  # Payme/Click/Bank ID

    source = Column(SAEnum(TransactionSource), nullable=False)
    status = Column(SAEnum(TransactionStatus), default=TransactionStatus.UNASSIGNED, nullable=False)

    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(10), default="UZS", nullable=False)

    paid_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True)

    raw_payload = Column(JSON, nullable=True)
    comment = Column(Text, nullable=True)

    student = relationship("Student", back_populates="transactions")
    contract = relationship("Contract")
