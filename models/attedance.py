from enum import Enum
from sqlalchemy import (
    Column, Integer, ForeignKey, Date, Time, DateTime,
    Boolean, Enum as SAEnum, JSON, String, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base, TimestampMixin


class SessionStatus(str, Enum):
    PLANNED = "PLANNED"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


class TrainingSession(TimestampMixin, Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)

    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    status = Column(SAEnum(SessionStatus), default=SessionStatus.PLANNED, nullable=False)

    group = relationship("Group", back_populates="sessions")
    attendance_records = relationship(
        "AttendanceRecord",
        back_populates="session",
        cascade="all, delete-orphan"
    )


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"


class AttendanceRecord(TimestampMixin, Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)

    status = Column(SAEnum(AttendanceStatus), nullable=False)
    comment = Column(Text, nullable=True)

    marked_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    session = relationship("TrainingSession", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")
    marked_by = relationship("User")  # Coach


class GateDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


class GateReason(str, Enum):
    OK = "OK"
    NO_PAYMENT = "NO_PAYMENT"
    NO_CONTRACT = "NO_CONTRACT"
    MANUAL = "MANUAL"
    OTHER = "OTHER"


class GateLog(TimestampMixin, Base):
    __tablename__ = "gate_logs"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)

    direction = Column(SAEnum(GateDirection), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    allowed = Column(Boolean, nullable=False, default=False)
    reason = Column(SAEnum(GateReason), nullable=False, default=GateReason.OK)

    raw_payload = Column(JSON, nullable=True)

    student = relationship("Student", back_populates="gate_logs")
