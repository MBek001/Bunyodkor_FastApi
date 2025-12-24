from typing import Annotated
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import joinedload
from datetime import datetime
import base64
from sqlalchemy import String

from app.core.db import get_db
from app.core.config import settings
from app.models.domain import Contract, Student
from app.models.finance import Transaction
from app.models.enums import PaymentSource, PaymentStatus, ContractStatus

router = APIRouter(prefix="/payme", tags=["Payme Payment"])


class PaymeError:
    INVALID_AMOUNT = -31001
    INVALID_ACCOUNT = -31050
    COULD_NOT_PERFORM = -31008
    TRANSACTION_NOT_FOUND = -31003
    INVALID_AUTHORIZATION = -32504
    METHOD_NOT_FOUND = -32601
    PARSE_ERROR = -32700
    INVALID_PARAMS = -32602


def check_authorization(request: Request) -> bool:
    """Payme autentifikatsiyasini tekshirish"""
    auth_header = request.headers.get("Authorization", "")
    x_auth = request.headers.get("X-Auth", "")

    if x_auth:
        return x_auth == settings.PAYME_KEY

    if not auth_header or not auth_header.startswith("Basic "):
        return False

    try:
        encoded = auth_header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("utf-8")

        if ":" not in decoded:
            return False

        login, password = decoded.split(":", 1)
        return login == "Paycom" and password == settings.PAYME_KEY
    except Exception:
        return False


def create_error_response(error_code: int, message: str, request_id: int = None):
    response = {
        "error": {
            "code": error_code,
            "message": message
        }
    }
    if request_id is not None:
        response["id"] = request_id
    return response


def create_success_response(result: dict, request_id: int):
    return {
        "result": result,
        "id": request_id
    }


@router.post("/payment")
async def payme_payment(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_db)]
):
    """Payme'dan kelgan barcha so'rovlarni handle qilish"""
    try:
        body = await request.json()
    except Exception:
        return create_error_response(PaymeError.PARSE_ERROR, "Ошибка разбора JSON")

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")

    if not method:
        return create_error_response(
            PaymeError.METHOD_NOT_FOUND, "Метод не найден", request_id
        )

    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий для выполнения метода",
            request_id
        )

    # Metodlarni route qilish
    if method == "GetStatement":
        return await get_statement(params, request_id, db)
    elif method == "CheckPerformTransaction":
        return await check_perform_transaction(params, request_id, db)
    elif method == "CreateTransaction":
        return await create_transaction(params, request_id, db)
    elif method == "PerformTransaction":
        return await perform_transaction(params, request_id, db)
    elif method == "CheckTransaction":
        return await check_transaction(params, request_id, db)
    elif method == "CancelTransaction":
        return await cancel_transaction(params, request_id, db)
    else:
        return create_error_response(
            PaymeError.METHOD_NOT_FOUND, "Метод не найден", request_id
        )


async def get_statement(params: dict, request_id: int, db: AsyncSession):
    """
    ✅ Student va to'lanmagan oylar haqida ma'lumot berish

    Parametrlar:
    - contract: Shartnoma raqami (masalan, "NB12011")
    - archive_year: Shartnoma yili (masalan, 2025 yoki 2026)
    - payment_year: To'lov yili (agar berilmasa, archive_year ishlatiladi)
    """
    account = params.get("account", {})

    contract_number = account.get("contract")
    if not contract_number:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Номер договора не указан",
            request_id
        )

    # archive_year - shartnoma qaysi yilga tegishli
    archive_year = account.get("archive_year")
    if not archive_year:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Год договора (archive_year) не указан",
            request_id
        )

    try:
        archive_year = int(archive_year)
    except (TypeError, ValueError):
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверный год договора",
            request_id
        )

    print(f"📋 GetStatement: contract={contract_number}, archive_year={archive_year}")

    # 1. Shartnomani topish (contract_number + archive_year)
    contract_result = await db.execute(
        select(Contract)
        .options(joinedload(Contract.student))
        .where(
            Contract.contract_number == contract_number,
            Contract.archive_year == archive_year
        )
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return {
            "error": {
                "code": -31050,
                "message": {
                    "ru": f"Договор {contract_number} за {archive_year} год не найден",
                    "uz": f"{contract_number} shartnoma {archive_year} yil uchun topilmadi",
                    "en": f"Contract {contract_number} for year {archive_year} not found"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    # 2. DELETED statusni tekshirish
    if contract.status == ContractStatus.DELETED:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Договор удален",
            request_id
        )

    # 3. Student ma'lumotlari
    student = contract.student

    # 4. To'langan oylarni aniqlash
    from datetime import date as date_class

    contract_start_month = date_class(
        contract.start_date.year, contract.start_date.month, 1
    )
    contract_end_month = date_class(
        contract.end_date.year, contract.end_date.month, 1
    )

    # SUCCESS to'lovlarni olish
    paid_transactions = await db.execute(
        select(Transaction).where(
            Transaction.contract_id == contract.id,
            Transaction.status == PaymentStatus.SUCCESS
        )
    )
    paid_transactions = paid_transactions.scalars().all()

    # To'langan oylar to'plami
    paid_months = set()
    for t in paid_transactions:
        if t.payment_months:
            paid_months.update(t.payment_months)

    # 5. Barcha oylar
    month_names_ru = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }

    month_names_uz = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
        9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
    }

    available_months = []
    current_month_date = contract_start_month
    while current_month_date <= contract_end_month:
        month = current_month_date.month
        is_paid = month in paid_months

        available_months.append({
            "month": month,
            "month_name_ru": month_names_ru[month],
            "month_name_uz": month_names_uz[month],
            "amount": int(contract.monthly_fee * 100),
            "status": "paid" if is_paid else "unpaid"
        })

        if month == 12:
            current_month_date = date_class(current_month_date.year + 1, 1, 1)
        else:
            current_month_date = date_class(current_month_date.year, month + 1, 1)

    return create_success_response(
        {
            "contract": {
                "number": contract.contract_number,
                "archive_year": contract.archive_year,
                "status": contract.status.value,
                "start_date": contract.start_date.isoformat(),
                "end_date": contract.end_date.isoformat(),
                "monthly_fee": int(contract.monthly_fee * 100)
            },
            "student": {
                "name": f"{student.first_name} {student.last_name}",
                "phone": getattr(student, 'phone', None),
                "birth_year": student.date_of_birth.year if student.date_of_birth else None
            },
            "months": available_months,
            "total_months": len(available_months),
            "total_unpaid": len([m for m in available_months if m["status"] == "unpaid"]),
            "total_paid": len([m for m in available_months if m["status"] == "paid"])
        },
        request_id
    )


async def check_perform_transaction(params: dict, request_id: int, db: AsyncSession):
    """
    ✅ To'lov qilish mumkinligini tekshirish

    Parametrlar:
    - contract: Shartnoma raqami
    - archive_year: Shartnoma yili (2025, 2026, ...)
    - payment_month: To'lov oyi (1-12)
    - payment_year: Qaysi yil uchun to'lov (masalan, 2026)
    - amount: To'lov summasi (tiyin)
    """
    amount = params.get("amount")
    account = params.get("account", {})

    if not amount or not account:
        return create_error_response(
            PaymeError.INVALID_PARAMS, "Неверные параметры", request_id
        )

    contract_number = account.get("contract")
    archive_year = account.get("archive_year")
    payment_month = account.get("payment_month")
    payment_year = account.get("payment_year")

    # Validatsiya
    if not contract_number:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Номер договора обязателен",
            request_id
        )

    if not archive_year:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Год договора (archive_year) обязателен",
            request_id
        )

    if not payment_month:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Месяц оплаты обязателен",
            request_id
        )

    if not payment_year:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Год оплаты (payment_year) обязателен",
            request_id
        )

    try:
        archive_year = int(archive_year)
        payment_month = int(payment_month)
        payment_year = int(payment_year)
    except (TypeError, ValueError):
        return create_error_response(
            PaymeError.INVALID_PARAMS, "Неверные параметры", request_id
        )

    if not (1 <= payment_month <= 12):
        return create_error_response(
            PaymeError.INVALID_PARAMS, "Неверный месяц (1-12)", request_id
        )

    print(
        f"✅ CheckPerform: contract={contract_number}, archive_year={archive_year}, payment_month={payment_month}, payment_year={payment_year}")

    # 1. Shartnomani topish
    contract_result = await db.execute(
        select(Contract).where(
            Contract.contract_number == contract_number,
            Contract.archive_year == archive_year
        )
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return {
            "error": {
                "code": -31050,
                "message": {
                    "ru": f"Договор {contract_number} за {archive_year} год не найден",
                    "uz": f"{contract_number} shartnoma {archive_year} yil uchun topilmadi",
                    "en": f"Contract {contract_number} for year {archive_year} not found"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    # 2. Status tekshiruvi - faqat DELETED bo'lsa rad etish
    if contract.status == ContractStatus.DELETED:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Договор удален",
            request_id
        )

    # 3. Summa tekshiruvi
    amount_sum = float(amount)
    expected_amount = float(contract.monthly_fee * 100)

    if amount_sum != expected_amount:
        return create_error_response(
            PaymeError.INVALID_AMOUNT,
            f"Сумма должна быть равна {int(expected_amount)} тийин",
            request_id
        )

    # 4. Oy shartnoma davomida ekanligini tekshirish
    from datetime import date as date_class

    contract_start = date_class(contract.start_date.year, contract.start_date.month, 1)
    contract_end = date_class(contract.end_date.year, contract.end_date.month, 1)

    payment_months_in_contract = set()
    current = contract_start
    while current <= contract_end:
        payment_months_in_contract.add(current.month)
        if current.month == 12:
            current = date_class(current.year + 1, 1, 1)
        else:
            current = date_class(current.year, current.month + 1, 1)

    if payment_month not in payment_months_in_contract:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            f"Месяц {payment_month} не входит в период договора",
            request_id
        )

    # 5. Dublikat tekshiruvi - shu shartnoma uchun bu oy va yil to'langanmi?
    duplicate = await db.execute(
        select(Transaction).where(
            Transaction.contract_id == contract.id,
            Transaction.status == PaymentStatus.SUCCESS,
            Transaction.payment_year == payment_year,
            cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB))
        )
    )
    if duplicate.scalar_one_or_none():
        month_names = {
            1: "январь", 2: "февраль", 3: "март", 4: "апрель",
            5: "май", 6: "июнь", 7: "июль", 8: "август",
            9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
        }
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            f"Оплата за {month_names[payment_month]} {payment_year} года уже существует",
            request_id
        )

    return create_success_response({"allow": True}, request_id)


async def create_transaction(params: dict, request_id: int, db: AsyncSession):
    """
    ✅ Yangi tranzaksiya yaratish
    """
    payme_id = params.get("id")
    time = params.get("time")
    amount = params.get("amount")
    account = params.get("account", {})

    if not all([payme_id, time, amount, account]):
        return create_error_response(
            PaymeError.INVALID_PARAMS, "Неверные параметры", request_id
        )

    contract_number = account.get("contract")
    archive_year = account.get("archive_year")
    payment_month = account.get("payment_month")
    payment_year = account.get("payment_year")

    if not all([contract_number, archive_year, payment_month, payment_year]):
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Номер договора, archive_year, payment_month и payment_year обязательны",
            request_id
        )

    try:
        archive_year = int(archive_year)
        payment_month = int(payment_month)
        payment_year = int(payment_year)
    except (TypeError, ValueError):
        return create_error_response(
            PaymeError.INVALID_PARAMS, "Неверные параметры", request_id
        )

    print(
        f"🔍 CreateTransaction: payme_id={payme_id}, contract={contract_number}, archive_year={archive_year}, payment_month={payment_month}, payment_year={payment_year}")

    # 1. Idempotency - shu payme_id bilan tranzaksiya bormi?
    existing_result = await db.execute(
        select(Transaction).where(Transaction.external_id == str(payme_id))
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        print(f"✅ Transaction exists: id={existing.id}, status={existing.status}")

        if existing.status == PaymentStatus.SUCCESS:
            return create_success_response(
                {
                    "create_time": int(existing.created_at.timestamp() * 1000),
                    "perform_time": int(existing.paid_at.timestamp() * 1000) if existing.paid_at else 0,
                    "cancel_time": 0,
                    "transaction": str(existing.id),
                    "state": 2,
                    "reason": None
                },
                request_id
            )

        if existing.status == PaymentStatus.CANCELLED:
            perform_time = 0
            if existing.paid_at:
                perform_time = int(existing.paid_at.timestamp() * 1000)
            return create_success_response(
                {
                    "create_time": int(existing.created_at.timestamp() * 1000),
                    "perform_time": perform_time,
                    "cancel_time": int(existing.updated_at.timestamp() * 1000) if existing.updated_at else 0,
                    "transaction": str(existing.id),
                    "state": -2,
                    "reason": 5
                },
                request_id
            )

        # PENDING
        return create_success_response(
            {
                "create_time": int(existing.created_at.timestamp() * 1000),
                "perform_time": 0,
                "cancel_time": 0,
                "transaction": str(existing.id),
                "state": 1,
                "reason": None
            },
            request_id
        )

    # 2. Shartnomani topish
    contract_result = await db.execute(
        select(Contract).where(
            Contract.contract_number == contract_number,
            Contract.archive_year == archive_year
        )
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return {
            "error": {
                "code": -31050,
                "message": {
                    "ru": f"Договор {contract_number} за {archive_year} год не найден",
                    "uz": f"{contract_number} shartnoma {archive_year} yil uchun topilmadi",
                    "en": f"Contract {contract_number} for year {archive_year} not found"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    # Status tekshiruvi
    if contract.status == ContractStatus.DELETED:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Договор удален",
            request_id
        )

    # 3. Summani tekshirish
    amount_sum = float(amount)
    expected_amount = float(contract.monthly_fee * 100)

    if amount_sum != expected_amount:
        return create_error_response(
            PaymeError.INVALID_AMOUNT,
            f"Сумма должна быть {int(expected_amount)}",
            request_id
        )

    # 4. BOSHQA pending tranzaksiyalarni tekshirish
    other_pending = await db.execute(
        select(Transaction).where(
            Transaction.contract_id == contract.id,
            Transaction.status == PaymentStatus.PENDING,
            Transaction.payment_year == payment_year,
            cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB)),
            Transaction.external_id != str(payme_id)
        )
    )
    if other_pending.scalars().first():
        return {
            "error": {
                "code": -31050,
                "message": {
                    "ru": "Для данного месяца уже существует ожидающая транзакция",
                    "uz": "Ushbu oy uchun kutilayotgan tranzaksiya mavjud",
                    "en": "Pending transaction already exists for this month"
                },
                "data": "account.payment_month"
            },
            "id": request_id
        }

    # 5. SUCCESS to'lovni tekshirish
    success_payment = await db.execute(
        select(Transaction).where(
            Transaction.contract_id == contract.id,
            Transaction.status == PaymentStatus.SUCCESS,
            Transaction.payment_year == payment_year,
            cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB))
        )
    )
    if success_payment.scalar_one_or_none():
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            f"Оплата за месяц {payment_month}/{payment_year} уже существует",
            request_id
        )

    # 6. Yangi tranzaksiya yaratish
    transaction = Transaction(
        external_id=str(payme_id),
        amount=amount_sum,
        source=PaymentSource.PAYME,
        status=PaymentStatus.PENDING,
        contract_id=contract.id,
        student_id=contract.student_id,
        payment_year=payment_year,
        payment_months=[payment_month],
        comment=f"Payme: contract {contract_number} (archive {archive_year}), payment for {payment_month}/{payment_year}"
    )

    db.add(transaction)

    try:
        await db.commit()
        await db.refresh(transaction)
        print(f"✅ Transaction created: id={transaction.id}")
    except Exception as e:
        await db.rollback()
        print(f"❌ Error: {e}")
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM, "Ошибка создания транзакции", request_id
        )

    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": 0,
            "cancel_time": 0,
            "transaction": str(transaction.id),
            "state": 1,
            "reason": None
        },
        request_id
    )



async def perform_transaction(params: dict, request_id: int, db: AsyncSession):
    """Tranzaksiyani tasdiqlash"""
    payme_id = params.get("id")

    if not payme_id:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверные параметры",
            request_id
        )

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.external_id == str(payme_id)
        )
    )
    transaction = transaction_result.scalar_one_or_none()

    if not transaction:
        return create_error_response(
            PaymeError.TRANSACTION_NOT_FOUND,
            "Транзакция не найдена",
            request_id
        )

    if transaction.status == PaymentStatus.SUCCESS:
        return create_success_response(
            {
                "create_time": int(transaction.created_at.timestamp() * 1000),
                "perform_time": int(transaction.paid_at.timestamp() * 1000) if transaction.paid_at else 0,
                "cancel_time": 0,
                "transaction": str(transaction.id),
                "state": 2,
                "reason": None
            },
            request_id
        )

    if transaction.status == PaymentStatus.CANCELLED:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Транзакция отменена",
            request_id
        )

    contract_result = await db.execute(
        select(Contract).where(Contract.id == transaction.contract_id)
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Договор не найден",
            request_id
        )

    if contract.status == ContractStatus.DELETED:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Договор удален",
            request_id
        )

    payment_year = transaction.payment_year
    payment_month = transaction.payment_months[0] if transaction.payment_months else datetime.now().month

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

        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Оплата за этот месяц уже существует",
            request_id
        )

    transaction.status = PaymentStatus.SUCCESS
    transaction.paid_at = datetime.utcnow()
    transaction.comment = f"Payme confirmed: ID {payme_id}, month {payment_month}/{payment_year}"

    await db.commit()
    await db.refresh(transaction)

    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": int(transaction.paid_at.timestamp() * 1000),
            "cancel_time": 0,
            "transaction": str(transaction.id),
            "state": 2,
            "reason": None
        },
        request_id
    )




async def check_transaction(params: dict, request_id: int, db: AsyncSession):
    """Tranzaksiya holatini tekshirish"""
    payme_id = params.get("id")

    print(f"🔍 CheckTransaction: Looking for payme_id = {payme_id}")

    if not payme_id:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверные параметры",
            request_id
        )

    transaction_result = await db.execute(
        select(Transaction).where(
            (Transaction.external_id == str(payme_id)) |
            (cast(Transaction.id, String) == str(payme_id))
        )
    )

    transaction = transaction_result.scalar_one_or_none()

    if not transaction:
        print(f"❌ Transaction NOT FOUND for payme_id: {payme_id}")
        return create_error_response(
            PaymeError.TRANSACTION_NOT_FOUND,
            "Транзакция не найдена",
            request_id
        )

    # State 2 = SUCCESS (performed)
    if transaction.status == PaymentStatus.SUCCESS:
        return create_success_response(
            {
                "create_time": int(transaction.created_at.timestamp() * 1000),
                "perform_time": int(transaction.paid_at.timestamp() * 1000) if transaction.paid_at else 0,
                "cancel_time": 0,
                "transaction": str(transaction.id),
                "state": 2,
                "reason": None
            },
            request_id
        )

    # State -2 = CANCELLED
    if transaction.status == PaymentStatus.CANCELLED:
        # ✅ Agar tranzaksiya SUCCESS bo'lganidan keyin CANCELLED bo'lgan bo'lsa
        # perform_time ni qaytaramiz, aks holda 0
        perform_time = 0
        if transaction.paid_at:
            perform_time = int(transaction.paid_at.timestamp() * 1000)

        return create_success_response(
            {
                "create_time": int(transaction.created_at.timestamp() * 1000),
                "perform_time": perform_time,
                "cancel_time": int(transaction.updated_at.timestamp() * 1000) if transaction.updated_at else 0,
                "transaction": str(transaction.id),
                "state": -2,
                "reason": 5  # 5 = cancelled by timeout or other reason
            },
            request_id
        )

    # State 1 = PENDING
    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": 0,
            "cancel_time": 0,
            "transaction": str(transaction.id),
            "state": 1,
            "reason": None
        },
        request_id
    )


async def cancel_transaction(params: dict, request_id: int, db: AsyncSession):
    """Tranzaksiyani bekor qilish"""
    payme_id = params.get("id")
    reason = params.get("reason", 5)  # default reason

    if not payme_id:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверные параметры",
            request_id
        )

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.external_id == str(payme_id)
        )
    )
    transaction = transaction_result.scalar_one_or_none()

    if not transaction:
        return create_error_response(
            PaymeError.TRANSACTION_NOT_FOUND,
            "Транзакция не найдена",
            request_id
        )

    # ✅ Agar allaqachon bekor qilingan bo'lsa
    if transaction.status == PaymentStatus.CANCELLED:
        perform_time = 0
        if transaction.paid_at:
            perform_time = int(transaction.paid_at.timestamp() * 1000)

        return create_success_response(
            {
                "create_time": int(transaction.created_at.timestamp() * 1000),
                "perform_time": perform_time,
                "cancel_time": int(transaction.updated_at.timestamp() * 1000) if transaction.updated_at else 0,
                "transaction": str(transaction.id),
                "state": -2,
                "reason": reason
            },
            request_id
        )

    # ✅ Agar SUCCESS holatida bo'lsa, perform_time ni saqlaymiz
    perform_time = 0
    if transaction.status == PaymentStatus.SUCCESS and transaction.paid_at:
        perform_time = int(transaction.paid_at.timestamp() * 1000)

    # Bekor qilish
    transaction.status = PaymentStatus.CANCELLED
    transaction.comment = f"Cancelled by Payme: reason {reason}"
    await db.commit()
    await db.refresh(transaction)

    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": perform_time,
            "cancel_time": int(transaction.updated_at.timestamp() * 1000),
            "transaction": str(transaction.id),
            "state": -2,
            "reason": reason
        },
        request_id
    )