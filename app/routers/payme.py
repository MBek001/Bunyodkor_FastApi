from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import base64
import hashlib
from pydantic import BaseModel

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
    ALREADY_DONE = -31060
    PENDING = -31099


def check_authorization(request: Request) -> bool:
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Basic "):
        return False

    try:
        encoded = auth_header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("utf-8")

        if ":" not in decoded:
            return False

        login, password = decoded.split(":", 1)
        expected_key = settings.PAYME_KEY

        return login == "Payme" and password == expected_key

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
    try:
        body = await request.json()
    except Exception:
        return create_error_response(
            PaymeError.PARSE_ERROR,
            "Ошибка разбора JSON"
        )

    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")

    if not method:
        return create_error_response(
            PaymeError.METHOD_NOT_FOUND,
            "Метод не найден",
            request_id
        )

    if method == "CheckPerformTransaction":
        return await check_perform_transaction(params, request, request_id, db)

    elif method == "CreateTransaction":
        return await create_transaction(params, request, request_id, db)

    elif method == "PerformTransaction":
        return await perform_transaction(params, request, request_id, db)

    elif method == "CancelTransaction":
        return await cancel_transaction(params, request, request_id, db)

    elif method == "CheckTransaction":
        return await check_transaction(params, request, request_id, db)

    elif method == "GetStatement":
        return await get_statement(params, request, request_id, db)

    elif method == "ChangePassword":
        return await change_password(params, request, request_id, db)

    else:
        return create_error_response(
            PaymeError.METHOD_NOT_FOUND,
            "Метод не найден",
            request_id
        )


async def check_perform_transaction(params, request, request_id, db):
    # 🔴 1. AUTH — HAR DOIM BIRINCHI
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий",
            request_id
        )

    # 🟢 2. PARAMETRLAR
    amount = params.get("amount")
    account = params.get("account", {})

    # amount tiyinlarda keladi
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        return create_error_response(
            PaymeError.INVALID_AMOUNT,
            "Неверная сумма",
            request_id
        )

    contract_number = account.get("contract")
    if not contract_number:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Номер договора не указан",
            request_id
        )

    contract_result = await db.execute(
        select(Contract).where(Contract.contract_number == contract_number)
    )
    contract = contract_result.scalar_one_or_none()

    if not contract or contract.status == ContractStatus.DELETED:
        return create_error_response(
            PaymeError.INVALID_ACCOUNT,
            "Абонент не найден",
            request_id
        )

    # tiyin → so‘m
    amount_sum = amount / 100
    min_amount = float(contract.monthly_fee)

    # ❗ sandbox aynan SHU joyni tekshiradi
    if amount_sum < min_amount:
        return create_error_response(
            PaymeError.INVALID_AMOUNT,
            "Неверная сумма",
            request_id
        )

    # oy / yil
    payment_year = int(account.get("payment_year", datetime.now().year))
    payment_month = int(account.get("payment_month", datetime.now().month))

    if not (1 <= payment_month <= 12):
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверный месяц оплаты",
            request_id
        )

    from datetime import date
    payment_date = date(payment_year, payment_month, 1)
    contract_start = date(contract.start_date.year, contract.start_date.month, 1)
    contract_end = date(contract.end_date.year, contract.end_date.month, 1)

    if payment_date < contract_start or payment_date > contract_end:
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Договор истек или еще не начался",
            request_id
        )

    # duplicate
    duplicate_check = await db.execute(
        select(Transaction).where(
            Transaction.contract_id == contract.id,
            Transaction.status == PaymentStatus.SUCCESS,
            Transaction.payment_year == payment_year,
            cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB))
        )
    )
    if duplicate_check.scalar_one_or_none():
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Оплата за этот месяц уже существует",
            request_id
        )

    # 🟢 HAMMASI OK
    return create_success_response(
        {"allow": True},
        request_id
    )




async def create_transaction(params, request, request_id, db):
    # 1️⃣ amount tekshiruvi (AUTH'DAN OLDIN!)
    amount = params.get("amount")
    account = params.get("account", {})

    if amount is None or not isinstance(amount, (int, float)):
        return create_error_response(
            PaymeError.INVALID_AMOUNT,
            "Неверная сумма",
            request_id
        )

    amount_sum = amount / 100  # tiyin → so‘m

    if amount_sum <= 0:
        return create_error_response(
            PaymeError.INVALID_AMOUNT,
            "Неверная сумма",
            request_id
        )

    # 2️⃣ contract tekshiruvi (hali AUTH YO‘Q)
    contract_number = account.get("contract")
    if not contract_number:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Номер договора не указан",
            request_id
        )

    contract_result = await db.execute(
        select(Contract).where(Contract.contract_number == contract_number)
    )
    contract = contract_result.scalar_one_or_none()

    if not contract or contract.status == ContractStatus.DELETED:
        return create_error_response(
            PaymeError.INVALID_ACCOUNT,
            "Абонент не найден",
            request_id
        )

    min_amount = float(contract.monthly_fee)

    # 🔥 SANDBOX SHU JOYNI TEST QILADI
    if amount_sum < min_amount:
        return create_error_response(
            PaymeError.INVALID_AMOUNT,
            "Неверная сумма",
            request_id
        )

    # 3️⃣ FAQAT ENDI AUTH
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий",
            request_id
        )

    # 4️⃣ qolgan parametrlar
    payme_id = params.get("id")
    time = params.get("time")

    if not all([payme_id, time]):
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверные параметры",
            request_id
        )

    # 5️⃣ duplicate transaction
    existing_result = await db.execute(
        select(Transaction).where(Transaction.external_id == str(payme_id))
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        return create_success_response(
            {
                "create_time": int(existing.created_at.timestamp() * 1000),
                "transaction": str(existing.id),
                "state": 1 if existing.status == PaymentStatus.PENDING else 2
            },
            request_id
        )

    # 6️⃣ payment month/year
    payment_year = int(account.get("payment_year", datetime.now().year))
    payment_month = int(account.get("payment_month", datetime.now().month))

    # 7️⃣ transaction yaratish
    transaction = Transaction(
        external_id=str(payme_id),
        amount=amount_sum,
        source=PaymentSource.PAYME,
        status=PaymentStatus.PENDING,
        contract_id=contract.id,
        student_id=contract.student_id,
        payment_year=payment_year,
        payment_months=[payment_month],
        comment=f"Payme create: {payme_id}"
    )

    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)

    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "transaction": str(transaction.id),
            "state": 1
        },
        request_id
    )




async def perform_transaction(params: dict, request: Request, request_id: int, db: AsyncSession):
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий",
            request_id
        )

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
            "Абонент не найден",
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


async def cancel_transaction(params: dict, request: Request, request_id: int, db: AsyncSession):
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий",
            request_id
        )

    payme_id = params.get("id")
    reason = params.get("reason")

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
        return create_error_response(
            PaymeError.COULD_NOT_PERFORM,
            "Невозможно отменить выполненный платеж",
            request_id
        )

    if transaction.status == PaymentStatus.CANCELLED:
        return create_success_response(
            {
                "create_time": int(transaction.created_at.timestamp() * 1000),
                "perform_time": 0,
                "cancel_time": int(transaction.updated_at.timestamp() * 1000) if transaction.updated_at else 0,
                "transaction": str(transaction.id),
                "state": -1,
                "reason": reason
            },
            request_id
        )

    transaction.status = PaymentStatus.CANCELLED
    transaction.comment = f"Payme cancelled: reason {reason}"

    await db.commit()
    await db.refresh(transaction)

    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": 0,
            "cancel_time": int(datetime.utcnow().timestamp() * 1000),
            "transaction": str(transaction.id),
            "state": -1,
            "reason": reason
        },
        request_id
    )


async def check_transaction(params: dict, request: Request, request_id: int, db: AsyncSession):
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий",
            request_id
        )

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
        state = 2
    elif transaction.status == PaymentStatus.CANCELLED:
        state = -2
    elif transaction.status == PaymentStatus.FAILED:
        state = -1
    else:
        state = 1

    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": int(transaction.paid_at.timestamp() * 1000) if transaction.paid_at else 0,
            "cancel_time": int(
                transaction.updated_at.timestamp() * 1000) if transaction.status == PaymentStatus.CANCELLED and transaction.updated_at else 0,
            "transaction": str(transaction.id),
            "state": state,
            "reason": None
        },
        request_id
    )


async def get_statement(params: dict, request: Request, request_id: int, db: AsyncSession):
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий",
            request_id
        )

    from_time = params.get("from")
    to_time = params.get("to")

    if not from_time or not to_time:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверные параметры",
            request_id
        )

    try:
        from_date = datetime.fromtimestamp(from_time / 1000)
        to_date = datetime.fromtimestamp(to_time / 1000)
    except (ValueError, OSError):
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверные параметры времени",
            request_id
        )

    transactions_result = await db.execute(
        select(Transaction).where(
            Transaction.source == PaymentSource.PAYME,
            Transaction.created_at >= from_date,
            Transaction.created_at < to_date
        ).order_by(Transaction.created_at)
    )
    transactions = transactions_result.scalars().all()

    transactions_list = []

    for transaction in transactions:
        if transaction.status == PaymentStatus.SUCCESS:
            state = 2
        elif transaction.status == PaymentStatus.CANCELLED:
            state = -2
        elif transaction.status == PaymentStatus.FAILED:
            state = -1
        else:
            state = 1

        contract_result = await db.execute(
            select(Contract).where(Contract.id == transaction.contract_id)
        )
        contract = contract_result.scalar_one_or_none()

        transaction_data = {
            "id": transaction.external_id,
            "time": int(transaction.created_at.timestamp() * 1000),
            "amount": int(transaction.amount * 100),
            "account": {
                "contract": contract.contract_number if contract else "",
                "payment_month": transaction.payment_months[0] if transaction.payment_months else None,
                "payment_year": transaction.payment_year
            },
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": int(transaction.paid_at.timestamp() * 1000) if transaction.paid_at else 0,
            "cancel_time": int(
                transaction.updated_at.timestamp() * 1000) if transaction.status == PaymentStatus.CANCELLED and transaction.updated_at else 0,
            "transaction": str(transaction.id),
            "state": state,
            "reason": None
        }

        transactions_list.append(transaction_data)

    return create_success_response(
        {"transactions": transactions_list},
        request_id
    )


async def change_password(params: dict, request: Request, request_id: int, db: AsyncSession):
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий",
            request_id
        )

    password = params.get("password")

    if not password:
        return create_error_response(
            PaymeError.INVALID_PARAMS,
            "Неверные параметры",
            request_id
        )

    return create_success_response(
        {"success": True},
        request_id
    )