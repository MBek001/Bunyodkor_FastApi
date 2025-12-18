from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, cast
from sqlalchemy.dialects.postgresql import JSONB
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
class ClickRequest(BaseModel):
    action: int
    click_paydoc_id: int | None = None
    attempt_trans_id: int | None = None
    service_id: int
    merchant_prepare_id: int | None = None
    merchant_confirm_id: int | None = None
    sign_time: str | None = None
    sign_string: str | None = None
    params: dict | None = None
    from_date: str | None = None
    till_date: str | None = None


# =========================
# CONSTANTS
# =========================
# Click params order for paramsIV calculation
# CRITICAL: Must match the order Click sends params
PARAMS_ORDER = ["contract", "full_name", "service_type", "amount"]


# =========================
# HELPERS
# =========================
def md5_hash(value: str) -> str:
    """Generate MD5 hash"""
    return hashlib.md5(value.encode()).hexdigest()


def get_params_iv(params: dict) -> str:
    """
    Get all values from params dict in FIXED order
    paramsIV = all values of params object in transmitted order

    CRITICAL: dict.values() order is not guaranteed to match Click's order
    We must use a fixed order that matches Click's specification
    """
    if not params:
        return ""
    return "".join(str(params[k]) for k in PARAMS_ORDER if k in params)


def verify_signature(data: ClickRequest) -> bool:
    """
    Verify Click signature according to ADVANCED SHOP documentation:
    md5(
        click_paydoc_id +
        attempt_trans_id +
        service_id +
        SECRET_KEY +
        paramsIV +
        action +
        sign_time
    )
    paramsIV = all values from params dict in transmitted order
    """
    click_paydoc_id = str(data.click_paydoc_id or "")
    attempt_trans_id = str(data.attempt_trans_id or "")
    service_id = str(data.service_id)
    secret_key = settings.CLICK_SECRET_KEY
    params_iv = get_params_iv(data.params or {})
    action = str(data.action)
    sign_time = str(data.sign_time or "")

    # Build raw string according to documentation
    raw = (
        f"{click_paydoc_id}"
        f"{attempt_trans_id}"
        f"{service_id}"
        f"{secret_key}"
        f"{params_iv}"
        f"{action}"
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
    Click payment webhook endpoint - ADVANCED SHOP API

    Actions:
    - 0: Getinfo - Get information about contract (optional, no signature required)
    - 1: Prepare - Create transaction and get payment details (signature required)
    - 2: Confirm - Confirm transaction (signature required)
    - 3: Check - Check transaction status (signature required)
    - 4: Compare - Get reconciliation report (no signature required)
    """
    action = data.action

    # =========================
    # SECURITY: Validate service_id
    # =========================
    if str(data.service_id) != settings.CLICK_SERVICE_ID:
        return {
            "error": -3,
            "error_note": "Action not found"
        }

    # =========================
    # ACTION 0: GETINFO
    # =========================
    if action == 0:
        # No signature verification for Getinfo
        if not data.params or "contract" not in data.params:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        contract_number = data.params.get("contract")

        # Find contract
        contract_result = await db.execute(
            select(Contract).where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        # Get student info
        student_result = await db.execute(
            select(Student).where(Student.id == contract.student_id)
        )
        student = student_result.scalar_one_or_none()

        if not student:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        return {
            "error": 0,
            "error_note": "Успешно",
            "params": {
                "contract": contract.contract_number,
                "full_name": f"{student.first_name} {student.last_name}",
                "phone": student.phone or "",
                "address": student.address or "",
                "monthly_fee": float(contract.monthly_fee),
                "contract_status": contract.status.value,
                "start_date": contract.start_date.isoformat(),
                "end_date": contract.end_date.isoformat()
            }
        }

    # =========================
    # ACTION 1: PREPARE
    # =========================
    elif action == 1:
        # Verify signature
        if not verify_signature(data):
            return {
                "error": -1,
                "error_note": "SIGN CHECK FAILED!"
            }

        if not data.params or "contract" not in data.params:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        contract_number = data.params.get("contract")

        # Convert amount to float (Click may send it as string)
        try:
            amount = float(data.params.get("amount"))
        except (TypeError, ValueError):
            return {
                "error": -2,
                "error_note": "Incorrect parameter amount"
            }

        # Find contract
        contract_result = await db.execute(
            select(Contract).where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        # Check if contract is active
        if contract.status != ContractStatus.ACTIVE:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        # Validate amount (amount is already float from try/except above)
        if amount < float(contract.monthly_fee):
            return {
                "error": -2,
                "error_note": f"Неверная сумма оплаты. Минимум: {contract.monthly_fee}"
            }

        # Validate payment month is within contract period
        current_date = datetime.now().date()
        current_year = datetime.now().year
        current_month = datetime.now().month

        if current_date < contract.start_date:
            return {
                "error": -5,
                "error_note": f"Договор еще не начался. Начало: {contract.start_date.isoformat()}"
            }

        if current_date > contract.end_date:
            return {
                "error": -5,
                "error_note": f"Договор истек. Окончание: {contract.end_date.isoformat()}"
            }

        # Check for duplicate payment for current month
        duplicate_check = await db.execute(
            select(Transaction).where(
                Transaction.contract_id == contract.id,
                Transaction.status == PaymentStatus.SUCCESS,
                Transaction.payment_year == current_year,
                Transaction.payment_months.op('@>')(cast([current_month], JSONB))
            )
        )
        duplicate = duplicate_check.scalar_one_or_none()

        if duplicate:
            month_names = {
                1: "январь", 2: "февраль", 3: "март", 4: "апрель",
                5: "май", 6: "июнь", 7: "июль", 8: "август",
                9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
            }
            return {
                "error": -4,
                "error_note": f"Оплата за {month_names[current_month]} {current_year} уже существует"
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
                    "error_note": "Уже оплачен"
                }
            if existing.status == PaymentStatus.CANCELLED:
                return {
                    "error": -9,
                    "error_note": "Транзакция отменена"
                }
            # Return existing prepare
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_prepare_id": existing.id,
                "error": 0,
                "error_note": "Успешно",
                "params": {}
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
            comment=f"Click prepare: attempt {data.attempt_trans_id}"
        )

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)

        return {
            "click_paydoc_id": data.click_paydoc_id,
            "attempt_trans_id": data.attempt_trans_id,
            "merchant_prepare_id": transaction.id,
            "error": 0,
            "error_note": "Успешно",
            "params": {}
        }

    # =========================
    # ACTION 2: CONFIRM
    # =========================
    elif action == 2:
        # Verify signature
        if not verify_signature(data):
            return {
                "error": -1,
                "error_note": "SIGN CHECK FAILED!"
            }

        merchant_prepare_id = data.merchant_prepare_id

        if not merchant_prepare_id:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        # Find transaction
        transaction_result = await db.execute(
            select(Transaction).where(Transaction.id == merchant_prepare_id)
        )
        transaction = transaction_result.scalar_one_or_none()

        if not transaction:
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        # FRAUD PROTECTION: Validate click_paydoc_id matches transaction
        if transaction.external_id != str(data.click_paydoc_id):
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        # Check if already confirmed
        if transaction.status == PaymentStatus.SUCCESS:
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_confirm_id": transaction.id,
                "error": -4,
                "error_note": "Уже оплачен"
            }

        # Check if cancelled
        if transaction.status == PaymentStatus.CANCELLED:
            return {
                "error": -9,
                "error_note": "Транзакция отменена"
            }

        # Get contract to verify it's still valid
        contract_result = await db.execute(
            select(Contract).where(Contract.id == transaction.contract_id)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        # Final validation: Check contract is still ACTIVE
        if contract.status != ContractStatus.ACTIVE:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        # Set payment year and month to current date
        current_year = datetime.now().year
        current_month = datetime.now().month
        current_date = datetime.now().date()

        # Validate payment date is still within contract period
        if current_date < contract.start_date or current_date > contract.end_date:
            return {
                "error": -5,
                "error_note": "Договор истек или еще не начался"
            }

        # Final check: Ensure no duplicate payment was created between PREPARE and CONFIRM
        final_duplicate_check = await db.execute(
            select(Transaction).where(
                Transaction.contract_id == contract.id,
                Transaction.status == PaymentStatus.SUCCESS,
                Transaction.payment_year == current_year,
                Transaction.payment_months.op('@>')(cast([current_month], JSONB))
            )
        )
        final_duplicate = final_duplicate_check.scalar_one_or_none()

        if final_duplicate:
            # Cancel this transaction and return error
            transaction.status = PaymentStatus.CANCELLED
            transaction.comment = f"Cancelled: duplicate payment for month {current_month}"
            await db.commit()
            return {
                "error": -4,
                "error_note": "Оплата за этот месяц уже существует"
            }

        # Confirm transaction
        transaction.status = PaymentStatus.SUCCESS
        transaction.paid_at = datetime.utcnow()
        transaction.payment_year = current_year
        transaction.payment_months = [current_month]
        transaction.comment = f"Click confirmed: attempt {data.attempt_trans_id}, month {current_month}/{current_year}"

        await db.commit()
        await db.refresh(transaction)

        return {
            "click_paydoc_id": data.click_paydoc_id,
            "attempt_trans_id": data.attempt_trans_id,
            "merchant_confirm_id": transaction.id,
            "error": 0,
            "error_note": "Успешно",
            "params": {}
        }

    # =========================
    # ACTION 3: CHECK
    # =========================
    elif action == 3:
        # Verify signature
        if not verify_signature(data):
            return {
                "error": -1,
                "error_note": "SIGN CHECK FAILED!"
            }

        merchant_prepare_id = data.merchant_prepare_id

        if not merchant_prepare_id:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        # Find transaction
        transaction_result = await db.execute(
            select(Transaction).where(Transaction.id == merchant_prepare_id)
        )
        transaction = transaction_result.scalar_one_or_none()

        if not transaction:
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        # Determine status
        # 0 – запрос еще не обрабатывался (Click попробует допровести платеж)
        # 1 – была неуспешная попытка обработки запроса (Сlick отменит платеж)
        # 2 – запрос успешно обработан (Click отметит платеж успешным)

        if transaction.status == PaymentStatus.SUCCESS:
            status = 2
        elif transaction.status == PaymentStatus.CANCELLED or transaction.status == PaymentStatus.FAILED:
            status = 1
        else:  # PENDING or UNASSIGNED
            status = 0

        return {
            "click_paydoc_id": data.click_paydoc_id,
            "attempt_trans_id": data.attempt_trans_id,
            "error": 0,
            "error_note": "Успешно",
            "status": status,
            "params": {}
        }

    # =========================
    # ACTION 4: COMPARE
    # =========================
    elif action == 4:
        # No signature verification for Compare
        from_date_str = data.from_date
        till_date_str = data.till_date

        if not from_date_str or not till_date_str:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        try:
            # Parse dates
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d %H:%M:%S")
            till_date = datetime.strptime(till_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        # Get all successful Click transactions in the date range
        transactions_result = await db.execute(
            select(Transaction).where(
                and_(
                    Transaction.source == PaymentSource.CLICK,
                    Transaction.status == PaymentStatus.SUCCESS,
                    Transaction.paid_at.is_not(None),
                    Transaction.paid_at >= from_date,
                    Transaction.paid_at < till_date
                )
            )
        )
        transactions = transactions_result.scalars().all()

        # Build requests object
        requests = {}
        for transaction in transactions:
            if transaction.external_id:
                # Get contract
                contract_result = await db.execute(
                    select(Contract).where(Contract.id == transaction.contract_id)
                )
                contract = contract_result.scalar_one_or_none()

                if contract:
                    requests[transaction.external_id] = {
                        "click_paydoc_id": int(transaction.external_id),
                        "params": {
                            "contract": contract.contract_number,
                            "amount": float(transaction.amount)
                        }
                    }

        return {
            "error": 0,
            "error_note": "Успешно",
            "requests": requests
        }

    # =========================
    # UNKNOWN ACTION
    # =========================
    else:
        return {
            "error": -3,
            "error_note": "Действие не найдено"
        }
