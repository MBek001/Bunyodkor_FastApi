from datetime import date
from typing import Optional
from pydantic import BaseModel


class PublicContractInfo(BaseModel):
    contract_number: str
    student_first_name: str
    student_last_name: str
    monthly_fee: float
    start_date: date
    end_date: date
    current_debt: float
    last_payment_date: Optional[date] = None


class PublicPaymentInitiate(BaseModel):
    contract_number: str
    amount: float


class PaymentCallbackPayme(BaseModel):
    method: str
    params: dict


class PaymentCallbackClick(BaseModel):
    click_trans_id: str
    merchant_trans_id: str
    amount: float
    action: int
    error: int
    error_note: str
    sign_time: str
    sign_string: str
