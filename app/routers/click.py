from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import hashlib
from pydantic import BaseModel

from app.core.db import get_db
from app.core.config import settings
from app.models.domain import Contract, Student
from app.models.finance import Transaction
from app.models.enums import PaymentSource, PaymentStatus, ContractStatus

router = APIRouter(prefix="/click", tags=["Click Payment"])


# =========================
# PYDANTIC SCHEMAS
# =========================
class ClickParams(BaseModel):
    contract: str
    amount: float | None = None


class ClickRequest(BaseModel):
    click_paydoc_id: int
    attempt_trans_id: int | None = None
    service_id: int
    click_trans_id: int | None = None
    merchant_trans_id: str | None = None
    merchant_prepare_id: int | None = None
    merchant_confirm_id: int | None = None
    amount: float
    action: int
    error: int | None = None
    error_note: str | None = None
    sign_time: str
    sign_string: str
    params: dict


# =========================
# HELPERS
# =========================
def md5_hash(value: str) -> str:
    """Generate MD5 hash"""
    return hashlib.md5(value.encode()).hexdigest()


def verify_signature(data: ClickRequest, action: int) -> bool:
    """
    Verify Click signature according to documentation:
    md5(
        click_paydoc_id +
        attempt_trans_id +
        service_id +
        SECRET_KEY +
        merchant_trans_id +
        merchant_prepare_id +
        amount +
        action +
        sign_time
    )
    """
    # Get values from request
    click_paydoc_id = str(data.click_paydoc_id)
    attempt_trans_id = str(data.attempt_trans_id or "")
    service_id = str(data.service_id)
    secret_key = settings.CLICK_SECRET_KEY
    merchant_trans_id = str(data.merchant_trans_id or "")
    merchant_prepare_id = str(data.merchant_prepare_id or "")
    amount = str(data.amount)
    action_str = str(action)
    sign_time = str(data.sign_time)

    # Build raw string
    raw = (
        f"{click_paydoc_id}"
        f"{attempt_trans_id}"
        f"{service_id}"
        f"{secret_key}"
        f"{merchant_trans_id}"
        f"{merchant_prepare_id}"
        f"{amount}"
        f"{action_str}"
        f"{sign_time}"
    )

    calculated_sign = md5_hash(raw)
    return calculated_sign == data.sign_string


# =========================
# MAIN CLICK ENDPOINT
# =========================
@router.post("/payment")
async def click_payment(
    data: ClickRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Click payment webhook endpoint.

    Actions:
    - 0: Get information about contract
    - 1: Prepare transaction (create pending)
    - 2: Confirm transaction (mark as success)
    """
    action = data.action

    # =========================
    # 1️⃣ GET INFO (action = 0)
    # =========================
    if action == 0:
        contract_number = data.params.get("contract")

        if not contract_number:
            return {
                "error": -5,
                "error_note": "Contract number not provided"
            }

        # Find contract
        contract_result = await db.execute(
            select(Contract)
            .where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": "Contract not found"
            }

        # Check if contract is active
        if contract.status != ContractStatus.ACTIVE:
            return {
                "error": -9,
                "error_note": f"Contract is not active (status: {contract.status.value})"
            }

        # Get student info
        student_result = await db.execute(
            select(Student).where(Student.id == contract.student_id)
        )
        student = student_result.scalar_one_or_none()

        if not student:
            return {
                "error": -5,
                "error_note": "Student not found"
            }

        return {
            "error": 0,
            "error_note": "Success",
            "params": {
                "contract": contract.contract_number,
                "full_name": f"{student.first_name} {student.last_name}",
                "phone": student.phone or "",
                "monthly_fee": float(contract.monthly_fee),
                "contract_status": contract.status.value,
                "start_date": contract.start_date.isoformat(),
                "end_date": contract.end_date.isoformat()
            }
        }

    # =========================
    # 2️⃣ PREPARE (action = 1)
    # =========================
    elif action == 1:
        # Verify signature
        if not verify_signature(data, action):
            return {
                "error": -1,
                "error_note": "SIGN CHECK FAILED"
            }

        contract_number = data.params.get("contract")
        amount = data.amount

        if not contract_number:
            return {
                "error": -5,
                "error_note": "Contract number not provided"
            }

        # Find contract
        contract_result = await db.execute(
            select(Contract)
            .where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": "Contract not found"
            }

        # Check if contract is active
        if contract.status != ContractStatus.ACTIVE:
            return {
                "error": -9,
                "error_note": f"Contract is not active (status: {contract.status.value})"
            }

        # Validate amount (should be at least monthly fee)
        if amount < float(contract.monthly_fee):
            return {
                "error": -2,
                "error_note": f"Amount too small. Minimum: {contract.monthly_fee}"
            }

        # Check for existing transaction with same click_paydoc_id
        existing_result = await db.execute(
            select(Transaction).where(
                Transaction.external_id == str(data.click_paydoc_id)
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            if existing.status == PaymentStatus.SUCCESS:
                return {
                    "error": -4,
                    "error_note": "Already paid"
                }
            # Return existing prepare
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_prepare_id": existing.id,
                "error": 0,
                "error_note": "Success"
            }

        # Create new pending transaction
        transaction = Transaction(
            external_id=str(data.click_paydoc_id),
            amount=amount,
            source=PaymentSource.CLICK,
            status=PaymentStatus.PENDING,
            contract_id=contract.id,
            student_id=contract.student_id,
            payment_year=datetime.now().year,
            payment_months=[],  # Will be set on confirm
            comment=f"Click payment attempt: {data.attempt_trans_id}"
        )

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)

        return {
            "click_paydoc_id": data.click_paydoc_id,
            "attempt_trans_id": data.attempt_trans_id,
            "merchant_prepare_id": transaction.id,
            "error": 0,
            "error_note": "Success"
        }

    # =========================
    # 3️⃣ CONFIRM (action = 2)
    # =========================
    elif action == 2:
        # Verify signature
        if not verify_signature(data, action):
            return {
                "error": -1,
                "error_note": "SIGN CHECK FAILED"
            }

        merchant_prepare_id = data.merchant_prepare_id

        if not merchant_prepare_id:
            return {
                "error": -6,
                "error_note": "merchant_prepare_id not provided"
            }

        # Find transaction
        transaction_result = await db.execute(
            select(Transaction).where(Transaction.id == merchant_prepare_id)
        )
        transaction = transaction_result.scalar_one_or_none()

        if not transaction:
            return {
                "error": -6,
                "error_note": "Transaction not found"
            }

        # Check if already confirmed
        if transaction.status == PaymentStatus.SUCCESS:
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_confirm_id": transaction.id,
                "error": -4,
                "error_note": "Already confirmed"
            }

        # Check if cancelled
        if transaction.status == PaymentStatus.CANCELLED:
            return {
                "error": -9,
                "error_note": "Transaction was cancelled"
            }

        # Confirm transaction
        transaction.status = PaymentStatus.SUCCESS
        transaction.paid_at = datetime.utcnow()

        # Calculate payment months based on amount and monthly fee
        # For now, we'll need the client to specify which months
        # or we can set to current month
        current_month = datetime.now().month
        transaction.payment_months = [current_month]

        await db.commit()
        await db.refresh(transaction)

        return {
            "click_paydoc_id": data.click_paydoc_id,
            "attempt_trans_id": data.attempt_trans_id,
            "merchant_confirm_id": transaction.id,
            "error": 0,
            "error_note": "Success"
        }

    # =========================
    # ❌ UNKNOWN ACTION
    # =========================
    else:
        return {
            "error": -3,
            "error_note": "Action not found"
        }
