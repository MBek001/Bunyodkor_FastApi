from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.enums import ContractStatus


class TerminatedByUser(BaseModel):
    """User who terminated the contract"""
    id: int
    full_name: str

    class Config:
        from_attributes = True


class ContractRead(BaseModel):
    id: int
    contract_number: str
    start_date: date
    end_date: date
    monthly_fee: float
    status: ContractStatus
    student_id: int
    group_id: Optional[int] = None

    # Contract number allocation
    birth_year: int
    sequence_number: int

    # Document URLs
    passport_copy_url: Optional[str] = None
    form_086_url: Optional[str] = None
    heart_checkup_url: Optional[str] = None
    birth_certificate_url: Optional[str] = None
    contract_images_urls: Optional[str] = None  # JSON string

    # Digital signature
    signature_url: Optional[str] = None
    signature_token: Optional[str] = None
    signed_at: Optional[datetime] = None
    final_pdf_url: Optional[str] = None

    # Custom fields
    custom_fields: Optional[str] = None  # JSON string

    # Termination
    terminated_at: Optional[datetime] = None
    terminated_by_user_id: Optional[int] = None
    termination_reason: Optional[str] = None
    terminated_by: Optional[TerminatedByUser] = None

    created_at: datetime

    class Config:
        from_attributes = True


class ContractCreateWithDocuments(BaseModel):
    """Create contract with automatic number allocation and document uploads"""
    student_id: int
    group_id: int
    start_date: date
    end_date: date
    monthly_fee: float

    # Document URLs (uploaded separately first)
    passport_copy_url: Optional[str] = None
    form_086_url: Optional[str] = None
    heart_checkup_url: Optional[str] = None
    birth_certificate_url: Optional[str] = None
    contract_images_urls: Optional[List[str]] = Field(default=None, description="List of 5 contract page image URLs")

    # Admin-editable fields from handwritten parts
    custom_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom fields like parent info, payment details, etc."
    )


class ContractCreate(BaseModel):
    """Legacy contract creation (kept for backwards compatibility)"""
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
    custom_fields: Optional[Dict[str, Any]] = None


class ContractTerminate(BaseModel):
    termination_reason: str
    terminated_at: Optional[datetime] = None  # If not provided, will use current datetime


class ContractNumberInfo(BaseModel):
    """Information about available contract numbers"""
    group_id: int
    group_name: str
    group_capacity: int
    birth_year: int
    available_numbers: List[int]
    total_available: int
    total_used: int
    is_full: bool


class NextAvailableNumber(BaseModel):
    """Next available contract number"""
    next_available: Optional[int]
    contract_number: Optional[str]
    birth_year: int
    is_full: bool


class ContractCreatedResponse(BaseModel):
    """Response after creating a contract with documents"""
    contract: ContractRead
    signature_link: str
    message: str
    waiting_list: bool = False
