from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Date, Enum as SAEnum,
    ForeignKey, Numeric, Boolean
)
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin


class StudentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPELLED = "EXPELLED"
    GRADUATED = "GRADUATED"
    PAUSED = "PAUSED"


class StudentGender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class Student(TimestampMixin, Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    birth_date = Column(Date, nullable=True)
    gender = Column(SAEnum(StudentGender), nullable=True)

    status = Column(SAEnum(StudentStatus), default=StudentStatus.ACTIVE, nullable=False)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)

    group = relationship("Group", back_populates="students")
    parents = relationship("ParentContact", back_populates="student", cascade="all, delete-orphan")
    contracts = relationship("Contract", back_populates="student", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="student")
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    gate_logs = relationship("GateLog", back_populates="student")


class ParentContact(TimestampMixin, Base):
    __tablename__ = "parent_contacts"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)

    full_name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=False)
    relation = Column(String(50), nullable=True)

    student = relationship("Student", back_populates="parents")


class GroupStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Group(TimestampMixin, Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # masalan "U-12 A"
    coach_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    age_from = Column(Integer, nullable=True)  # optional
    age_to = Column(Integer, nullable=True)    # optional

    status = Column(SAEnum(GroupStatus), default=GroupStatus.ACTIVE, nullable=False)

    coach = relationship("User", back_populates="coached_groups")
    students = relationship("Student", back_populates="group")
    sessions = relationship("TrainingSession", back_populates="group")


class ContractStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True)
    contract_number = Column(String(50), unique=True, nullable=False)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    student = relationship("Student", back_populates="contracts")

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    monthly_fee = Column(Numeric(12, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=True)  # 0–100

    status = Column(SAEnum(ContractStatus), default=ContractStatus.ACTIVE, nullable=False)
