from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import selectinload
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
            "error_note": {
                "ru": "Сервис не найден",
                "uz": "Xizmat topilmadi",
                "en": "Service not found"
            }
        }

    # ACTION 0: Ma'lumot olish (Check)
    if action == 0:
        if not data.params or "contract" not in data.params:
            return {
                "error": -8,
                "error_note": {
                    "ru": "Ошибка в запросе от CLICK",
                    "uz": "CLICK dan so'rovda xatolik",
                    "en": "Error in request from CLICK"
                }
            }

        contract_number = data.params.get("contract")

        contract_result = await db.execute(
            select(Contract)
            .options(selectinload(Contract.student))
            .where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": {
                    "ru": "Договор не найден",
                    "uz": "Shartnoma topilmadi",
                    "en": "Contract not found"
                }
            }

        if contract.status != ContractStatus.ACTIVE:
            return {
                "error": -5,
                "error_note": {
                    "ru": "Договор не активен. Оплата возможна только по активным договорам",
                    "uz": "Shartnoma faol emas. To'lov faqat faol shartnomalar bo'yicha mumkin",
                    "en": "Contract is not active. Payment is only possible for active contracts"
                }
            }

        student = contract.student

        if not student:
            return {
                "error": -5,
                "error_note": {
                    "ru": "Студент не найден",
                    "uz": "Talaba topilmadi",
                    "en": "Student not found"
                }
            }

        return {
            "error": 0,
            "error_note": {
                "ru": "Успешно",
                "uz": "Muvaffaqiyatli",
                "en": "Success"
            },
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

    # ACTION 1: Prepare (Tayyorlash)
    elif action == 1:
        if not verify_signature(data):
            return {
                "error": -1,
                "error_note": {
                    "ru": "SIGN CHECK FAILED!",
                    "uz": "IMZO TEKSHIRUVI MUVAFFAQIYATSIZ!",
                    "en": "SIGN CHECK FAILED!"
                }
            }

        if not data.params or "contract" not in data.params:
            return {
                "error": -8,
                "error_note": {
                    "ru": "Ошибка в запросе от CLICK",
                    "uz": "CLICK dan so'rovda xatolik",
                    "en": "Error in request from CLICK"
                }
            }

        contract_number = data.params.get("contract")

        try:
            amount = float(data.params.get("amount"))
        except (TypeError, ValueError):
            return {
                "error": -2,
                "error_note": {
                    "ru": "Неверная сумма",
                    "uz": "Noto'g'ri summa",
                    "en": "Incorrect amount"
                }
            }

        contract_result = await db.execute(
            select(Contract)
            .options(selectinload(Contract.student))
            .where(Contract.contract_number == contract_number)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -5,
                "error_note": {
                    "ru": "Договор не найден",
                    "uz": "Shartnoma topilmadi",
                    "en": "Contract not found"
                }
            }

        if contract.status != ContractStatus.ACTIVE:
            return {
                "error": -5,
                "error_note": {
                    "ru": "Договор не активен",
                    "uz": "Shartnoma faol emas",
                    "en": "Contract is not active"
                }
            }

        # ✅ AYNAN TENG BO'LISHI KERAK (kam yoki ko'p emas)
        expected_amount = float(contract.monthly_fee)
        if amount != expected_amount:
            return {
                "error": -2,
                "error_note": {
                    "ru": f"Неверная сумма оплаты. Требуется ровно: {expected_amount}",
                    "uz": f"Noto'g'ri to'lov summasi. Aynan kerak: {expected_amount}",
                    "en": f"Incorrect payment amount. Required exactly: {expected_amount}"
                }
            }

        payment_year = data.params.get("payment_year")
        payment_month = data.params.get("payment_month")

        if payment_year is not None:
            try:
                payment_year = int(payment_year)
            except (TypeError, ValueError):
                return {
                    "error": -8,
                    "error_note": {
                        "ru": "Неверный год оплаты",
                        "uz": "Noto'g'ri to'lov yili",
                        "en": "Invalid payment year"
                    }
                }
        else:
            payment_year = datetime.now().year

        if payment_month is not None:
            try:
                payment_month = int(payment_month)
            except (TypeError, ValueError):
                return {
                    "error": -8,
                    "error_note": {
                        "ru": "Неверный месяц оплаты",
                        "uz": "Noto'g'ri to'lov oyi",
                        "en": "Invalid payment month"
                    }
                }
        else:
            payment_month = datetime.now().month

        if not (1 <= payment_month <= 12):
            return {
                "error": -8,
                "error_note": {
                    "ru": "Неверный месяц оплаты",
                    "uz": "Noto'g'ri to'lov oyi",
                    "en": "Invalid payment month"
                }
            }

        from datetime import date as date_class
        payment_date = date_class(payment_year, payment_month, 1)
        contract_start_month = date_class(contract.start_date.year, contract.start_date.month, 1)
        contract_end_month = date_class(contract.end_date.year, contract.end_date.month, 1)

        if payment_date < contract_start_month:
            return {
                "error": -5,
                "error_note": {
                    "ru": f"Договор еще не начался. Начало: {contract.start_date.isoformat()}",
                    "uz": f"Shartnoma hali boshlanmagan. Boshlanishi: {contract.start_date.isoformat()}",
                    "en": f"Contract has not started yet. Start: {contract.start_date.isoformat()}"
                }
            }

        if payment_date > contract_end_month:
            return {
                "error": -5,
                "error_note": {
                    "ru": f"Договор истек. Окончание: {contract.end_date.isoformat()}",
                    "uz": f"Shartnoma muddati tugagan. Tugash: {contract.end_date.isoformat()}",
                    "en": f"Contract expired. End: {contract.end_date.isoformat()}"
                }
            }

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
            month_names_ru = {
                1: "январь", 2: "февраль", 3: "март", 4: "апрель",
                5: "май", 6: "июнь", 7: "июль", 8: "август",
                9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
            }
            month_names_uz = {
                1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
                5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
                9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
            }
            month_names_en = {
                1: "January", 2: "February", 3: "March", 4: "April",
                5: "May", 6: "June", 7: "July", 8: "August",
                9: "September", 10: "October", 11: "November", 12: "December"
            }
            return {
                "error": -4,
                "error_note": {
                    "ru": f"Оплата за {month_names_ru[payment_month]} {payment_year} уже существует",
                    "uz": f"{month_names_uz[payment_month]} {payment_year} uchun to'lov allaqachon mavjud",
                    "en": f"Payment for {month_names_en[payment_month]} {payment_year} already exists"
                }
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
                    "error_note": {
                        "ru": "Уже оплачен",
                        "uz": "Allaqachon to'langan",
                        "en": "Already paid"
                    }
                }
            if existing.status == PaymentStatus.CANCELLED:
                return {
                    "error": -9,
                    "error_note": {
                        "ru": "Транзакция отменена",
                        "uz": "Tranzaksiya bekor qilingan",
                        "en": "Transaction cancelled"
                    }
                }
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_prepare_id": existing.id,
                "error": 0,
                "error_note": {
                    "ru": "Успешно",
                    "uz": "Muvaffaqiyatli",
                    "en": "Success"
                },
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
            "error_note": {
                "ru": "Успешно",
                "uz": "Muvaffaqiyatli",
                "en": "Success"
            },
            "params": {}
        }

    # ACTION 2: Complete (Tasdiqlash)
    elif action == 2:
        if not verify_signature(data):
            return {
                "error": -1,
                "error_note": {
                    "ru": "SIGN CHECK FAILED!",
                    "uz": "IMZO TEKSHIRUVI MUVAFFAQIYATSIZ!",
                    "en": "SIGN CHECK FAILED!"
                }
            }

        merchant_prepare_id = data.merchant_prepare_id

        if not merchant_prepare_id:
            return {
                "error": -8,
                "error_note": {
                    "ru": "Ошибка в запросе от CLICK",
                    "uz": "CLICK dan so'rovda xatolik",
                    "en": "Error in request from CLICK"
                }
            }

        transaction_result = await db.execute(
            select(Transaction).where(Transaction.id == merchant_prepare_id)
        )
        transaction = transaction_result.scalar_one_or_none()

        if not transaction:
            return {
                "error": -6,
                "error_note": {
                    "ru": "Транзакция не найдена",
                    "uz": "Tranzaksiya topilmadi",
                    "en": "Transaction not found"
                }
            }

        if transaction.external_id != str(data.click_paydoc_id):
            return {
                "error": -6,
                "error_note": {
                    "ru": "Транзакция не найдена",
                    "uz": "Tranzaksiya topilmadi",
                    "en": "Transaction not found"
                }
            }

        if transaction.status == PaymentStatus.SUCCESS:
            return {
                "click_paydoc_id": data.click_paydoc_id,
                "attempt_trans_id": data.attempt_trans_id,
                "merchant_confirm_id": transaction.id,
                "error": -4,
                "error_note": {
                    "ru": "Уже оплачен",
                    "uz": "Allaqachon to'langan",
                    "en": "Already paid"
                }
            }

        if transaction.status == PaymentStatus.CANCELLED:
            return {
                "error": -9,
                "error_note": {
                    "ru": "Транзакция отменена",
                    "uz": "Tranzaksiya bekor qilingan",
                    "en": "Transaction cancelled"
                }
            }

        contract_result = await db.execute(
            select(Contract).where(Contract.id == transaction.contract_id)
        )
        contract = contract_result.scalar_one_or_none()

        if not contract:
            return {
                "error": -6,
                "error_note": {
                    "ru": "Договор не найден",
                    "uz": "Shartnoma topilmadi",
                    "en": "Contract not found"
                }
            }

        if contract.status != ContractStatus.ACTIVE:
            return {
                "error": -5,
                "error_note": {
                    "ru": "Договор не активен",
                    "uz": "Shartnoma faol emas",
                    "en": "Contract is not active"
                }
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
                "error_note": {
                    "ru": "Договор истек или еще не начался",
                    "uz": "Shartnoma muddati tugagan yoki hali boshlanmagan",
                    "en": "Contract expired or not started yet"
                }
            }

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
                "error_note": {
                    "ru": "Оплата за этот месяц уже существует",
                    "uz": "Ushbu oy uchun to'lov allaqachon mavjud",
                    "en": "Payment for this month already exists"
                }
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
            "error_note": {
                "ru": "Успешно",
                "uz": "Muvaffaqiyatli",
                "en": "Success"
            },
            "params": {}
        }

    # Noma'lum action
    else:
        return {
            "error": -3,
            "error_note": {
                "ru": "Действие не найдено",
                "uz": "Harakat topilmadi",
                "en": "Action not found"
            }
        }