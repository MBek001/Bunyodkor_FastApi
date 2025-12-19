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


PARAMS_ORDER = ["contract", "full_name", "service_type", "amount", "payment_month", "payment_year"]


def md5_hash(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def get_params_iv(params: dict) -> str:
    if not params:
        return ""
    return "".join(str(params[k]) for k in PARAMS_ORDER if k in params)


def verify_signature(data: ClickRequest) -> bool:
    click_paydoc_id = str(data.click_paydoc_id or "")
    attempt_trans_id = str(data.attempt_trans_id or "")
    service_id = str(data.service_id)
    secret_key = settings.CLICK_SECRET_KEY
    params_iv = get_params_iv(data.params or {})
    action = str(data.action)
    sign_time = str(data.sign_time or "")

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


@router.post("/payment")
async def click_payment(
    data: ClickRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    action = data.action

    if str(data.service_id) != settings.CLICK_SERVICE_ID:
        return {
            "error": -3,
            "error_note": "Action not found"
        }

    if action == 0:
        if not data.params or "contract" not in data.params:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        contract_number = data.params.get("contract")

        contract_result = await db.execute(
            select(Contract).where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

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

    elif action == 1:
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

        try:
            amount = float(data.params.get("amount"))
        except (TypeError, ValueError):
            return {
                "error": -2,
                "error_note": "Incorrect parameter amount"
            }

        contract_result = await db.execute(
            select(Contract).where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        # Allow payments for ACTIVE, EXPIRED, TERMINATED, and ARCHIVED contracts
        # Only DELETED contracts cannot receive payments
        if contract.status == ContractStatus.DELETED:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        if amount < float(contract.monthly_fee):
            return {
                "error": -2,
                "error_note": f"Неверная сумма оплаты. Минимум: {contract.monthly_fee}"
            }

        payment_year = data.params.get("payment_year")
        payment_month = data.params.get("payment_month")

        if payment_year is not None:
            try:
                payment_year = int(payment_year)
            except (TypeError, ValueError):
                return {
                    "error": -8,
                    "error_note": "Ошибка в запросе от CLICK"
                }
        else:
            payment_year = datetime.now().year

        if payment_month is not None:
            try:
                payment_month = int(payment_month)
            except (TypeError, ValueError):
                return {
                    "error": -8,
                    "error_note": "Ошибка в запросе от CLICK"
                }
        else:
            payment_month = datetime.now().month

        if not (1 <= payment_month <= 12):
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        from datetime import date as date_class
        payment_date = date_class(payment_year, payment_month, 1)
        contract_start_month = date_class(contract.start_date.year, contract.start_date.month, 1)
        contract_end_month = date_class(contract.end_date.year, contract.end_date.month, 1)

        if payment_date < contract_start_month:
            return {
                "error": -5,
                "error_note": f"Договор еще не начался. Начало: {contract.start_date.isoformat()}"
            }

        if payment_date > contract_end_month:
            return {
                "error": -5,
                "error_note": f"Договор истек. Окончание: {contract.end_date.isoformat()}"
            }

        # Cast payment_months to JSONB to avoid type mismatch
        duplicate_check = await db.execute(
            select(Transaction).where(
                Transaction.contract_id == contract.id,
                Transaction.status == PaymentStatus.SUCCESS,
                Transaction.payment_year == payment_year,
                cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB))
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
                "error_note": f"Оплата за {month_names[payment_month]} {payment_year} уже существует"
            }

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
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_prepare_id": existing.id,
                "error": 0,
                "error_note": "Успешно",
                "params": {}
            }

        transaction = Transaction(
            external_id=str(data.click_paydoc_id),
            amount=amount,
            source=PaymentSource.CLICK,
            status=PaymentStatus.PENDING,
            contract_id=contract.id,
            student_id=contract.student_id,
            payment_year=payment_year,
            payment_months=[payment_month],
            comment=f"Click prepare: attempt {data.attempt_trans_id}, month {payment_month}/{payment_year}"
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

    elif action == 2:
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

        transaction_result = await db.execute(
            select(Transaction).where(Transaction.id == merchant_prepare_id)
        )
        transaction = transaction_result.scalar_one_or_none()

        if not transaction:
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        if transaction.external_id != str(data.click_paydoc_id):
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        if transaction.status == PaymentStatus.SUCCESS:
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_confirm_id": transaction.id,
                "error": -4,
                "error_note": "Уже оплачен"
            }

        if transaction.status == PaymentStatus.CANCELLED:
            return {
                "error": -9,
                "error_note": "Транзакция отменена"
            }

        contract_result = await db.execute(
            select(Contract).where(Contract.id == transaction.contract_id)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        # Allow payments for ACTIVE, EXPIRED, TERMINATED, and ARCHIVED contracts
        # Only DELETED contracts cannot receive payments
        if contract.status == ContractStatus.DELETED:
            return {
                "error": -5,
                "error_note": "Абонент не найден"
            }

        payment_year = transaction.payment_year
        payment_month = transaction.payment_months[0] if transaction.payment_months else datetime.now().month

        from datetime import date as date_class
        payment_date = date_class(payment_year, payment_month, 1)
        contract_start_month = date_class(contract.start_date.year, contract.start_date.month, 1)
        contract_end_month = date_class(contract.end_date.year, contract.end_date.month, 1)

        if payment_date < contract_start_month or payment_date > contract_end_month:
            return {
                "error": -5,
                "error_note": "Договор истек или еще не начался"
            }

        # Cast payment_months to JSONB to avoid type mismatch
        final_duplicate_check = await db.execute(
            select(Transaction).where(
                Transaction.contract_id == contract.id,
                Transaction.status == PaymentStatus.SUCCESS,
                Transaction.payment_year == payment_year,
                cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB)),
                Transaction.id != transaction.id
            )
        )
        final_duplicate = final_duplicate_check.scalar_one_or_none()

        if final_duplicate:
            transaction.status = PaymentStatus.CANCELLED
            transaction.comment = f"Cancelled: duplicate payment for month {payment_month}/{payment_year}"
            await db.commit()
            return {
                "error": -4,
                "error_note": "Оплата за этот месяц уже существует"
            }

        transaction.status = PaymentStatus.SUCCESS
        transaction.paid_at = datetime.utcnow()
        transaction.comment = f"Click confirmed: attempt {data.attempt_trans_id}, month {payment_month}/{payment_year}"

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

    elif action == 3:
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

        transaction_result = await db.execute(
            select(Transaction).where(Transaction.id == merchant_prepare_id)
        )
        transaction = transaction_result.scalar_one_or_none()

        if not transaction:
            return {
                "error": -6,
                "error_note": "Транзакция не найдена"
            }

        if transaction.status == PaymentStatus.SUCCESS:
            status = 2
        elif transaction.status == PaymentStatus.CANCELLED or transaction.status == PaymentStatus.FAILED:
            status = 1
        else:
            status = 0

        return {
            "click_paydoc_id": data.click_paydoc_id,
            "attempt_trans_id": data.attempt_trans_id,
            "error": 0,
            "error_note": "Успешно",
            "status": status,
            "params": {}
        }

    elif action == 4:
        from_date_str = data.from_date
        till_date_str = data.till_date

        if not from_date_str or not till_date_str:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

        try:
            from_date = datetime.strptime(from_date_str, "%Y-%m-%d %H:%M:%S")
            till_date = datetime.strptime(till_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return {
                "error": -8,
                "error_note": "Ошибка в запросе от CLICK"
            }

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

        requests = {}
        for transaction in transactions:
            if transaction.external_id:
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

    else:
        return {
            "error": -3,
            "error_note": "Действие не найдено"
        }
