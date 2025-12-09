from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class StudentStatus(str, Enum):
    ACTIVE = "active"
    GRADUATED = "graduated"
    DROPPED = "dropped"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"  # For yearly archiving


class GroupStatus(str, Enum):
    """Group status for yearly archiving"""
    ACTIVE = "active"
    ARCHIVED = "archived"


class ContractStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    ARCHIVED = "archived"  # For yearly archiving


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNASSIGNED = "unassigned"


class PaymentSource(str, Enum):
    PAYME = "payme"
    CLICK = "click"
    BANK = "bank"
    CASH = "cash"
    MANUAL = "manual"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
