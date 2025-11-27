from datetime import date
from sqlalchemy import String, Date, Integer, Numeric, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base
from app.models.base import TimestampMixin
from app.models.enums import StudentStatus, ContractStatus, DayOfWeek


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    face_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    status: Mapped[StudentStatus] = mapped_column(
        SAEnum(StudentStatus, native_enum=False, length=20), default=StudentStatus.ACTIVE, nullable=False
    )

    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)

    group: Mapped["Group"] = relationship("Group", back_populates="students")
    parents: Mapped[list["Parent"]] = relationship("Parent", back_populates="student")
    contracts: Mapped[list["Contract"]] = relationship("Contract", back_populates="student")
    attendances: Mapped[list["Attendance"]] = relationship("Attendance", back_populates="student")
    gate_logs: Mapped[list["GateLog"]] = relationship("GateLog", back_populates="student")


class Parent(Base, TimestampMixin):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relationship_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    student: Mapped["Student"] = relationship("Student", back_populates="parents")


class Group(Base, TimestampMixin):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_days: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schedule_time: Mapped[str | None] = mapped_column(String(50), nullable=True)

    coach_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    coach: Mapped["User"] = relationship("User")
    students: Mapped[list["Student"]] = relationship("Student", back_populates="group")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="group")


class Contract(Base, TimestampMixin):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contract_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    monthly_fee: Mapped[int] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        SAEnum(ContractStatus, native_enum=False, length=20), default=ContractStatus.ACTIVE, nullable=False
    )

    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    student: Mapped["Student"] = relationship("Student", back_populates="contracts")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="contract")
