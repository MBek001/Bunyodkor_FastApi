from typing import Annotated
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import selectinload
from datetime import datetime
import base64
from sqlalchemy import String

from app.core.db import get_db
from app.core.config import settings
from app.models.domain import Contract, Student
from app.models.finance import Transaction
from app.models.enums import PaymentSource, PaymentStatus, ContractStatus

router = APIRouter(prefix="/payme", tags=["Payme Payment"])

# Global o'zgaruvchi - parolni vaqtinchalik saqlash uchun
CURRENT_PAYME_PASSWORD = None


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
    global CURRENT_PAYME_PASSWORD

    auth_header = request.headers.get("Authorization", "")
    x_auth = request.headers.get("X-Auth", "")

    print(f"🔑 Authorization header: {auth_header}")
    print(f"🔑 X-Auth header: {x_auth}")
    print(f"📋 All headers: {dict(request.headers)}")

    # Joriy aktiv parolni aniqlash
    active_password = CURRENT_PAYME_PASSWORD if CURRENT_PAYME_PASSWORD else settings.PAYME_KEY
    print(f"🔐 Active password: {active_password}")

    if x_auth:
        result = x_auth == active_password
        print(f"✅ X-Auth check result: {result}")
        return result

    if not auth_header:
        print("❌ No auth headers found")
        return False

    if not auth_header.startswith("Basic "):
        print("❌ Auth header doesn't start with 'Basic '")
        return False

    try:
        encoded = auth_header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("utf-8")

        print(f"🔓 Decoded: {decoded}")

        if ":" not in decoded:
            print("❌ No colon in decoded string")
            return False

        login, password = decoded.split(":", 1)

        print(f"👤 Login: {login}")
        print(f"🔒 Password: {password}")

        result = login == "Paycom" and password == active_password
        print(f"✅ Basic Auth result: {result}")

        return result

    except Exception as e:
        print(f"❌ Exception: {e}")
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

    # ChangePassword uchun alohida tartib
    if method == "ChangePassword":
        return await change_password(params, request_id, request)

    # Qolgan metodlar uchun autorizatsiya
    if not check_authorization(request):
        return create_error_response(
            PaymeError.INVALID_AUTHORIZATION,
            "Недостаточно привилегий для выполнения метода",
            request_id
        )

    if method == "CheckPerformTransaction":
        return await check_perform_transaction(params, request_id, db)

    elif method == "CreateTransaction":
        return await create_transaction(params, request_id, db)

    elif method == "PerformTransaction":
        return await perform_transaction(params, request_id, db)

    elif method == "CheckTransaction":
        return await check_transaction(params, request_id, db)

    elif method == "CancelTransaction":
        return await cancel_transaction(params, request_id, db)
    elif method == "GetStatement":  # ✅ YANGI METOD
        return await get_statement(params, request_id, db)

    else:
        return create_error_response(
            PaymeError.METHOD_NOT_FOUND,
            "Метод не найден",
            request_id
        )


async def change_password(params: dict, request_id: int, request: Request):
    global CURRENT_PAYME_PASSWORD

    new_password = params.get("password")

    if not new_password:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Новый пароль не указан",
                    "uz": "Yangi parol ko'rsatilmagan",
                    "en": "New password not provided"
                }
            },
            "id": request_id
        }

    if not check_authorization(request):
        return {
            "error": {
                "code": PaymeError.INVALID_AUTHORIZATION,
                "message": {
                    "ru": "Недостаточно привилегий для выполнения метода",
                    "uz": "Usulni bajarish uchun huquqlar yetarli emas",
                    "en": "Insufficient privileges to execute method"
                }
            },
            "id": request_id
        }

    old_password = CURRENT_PAYME_PASSWORD if CURRENT_PAYME_PASSWORD else settings.PAYME_KEY
    CURRENT_PAYME_PASSWORD = new_password


    return create_success_response({"success": True}, request_id)


async def check_perform_transaction(params: dict, request_id: int, db: AsyncSession):
    """
    2 bosqichli tekshiruv:
    1. Faqat contract → student ma'lumotlarini ko'rsatish
    2. Contract + amount + year + month → to'lovni tasdiqlash
    """
    amount = params.get("amount")
    account = params.get("account", {})

    if not account:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверные параметры",
                    "uz": "Noto'g'ri parametrlar",
                    "en": "Invalid parameters"
                }
            },
            "id": request_id
        }

    contract_number = account.get("contract")

    if not contract_number:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Номер договора не указан",
                    "uz": "Shartnoma raqami ko'rsatilmagan",
                    "en": "Contract number not provided"
                }
            },
            "id": request_id
        }

    # Contract va Student ni olish
    contract_result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.student))
        .where(Contract.contract_number == contract_number)
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return {
            "error": {
                "code": PaymeError.INVALID_ACCOUNT,
                "message": {
                    "ru": "Договор не найден",
                    "uz": "Shartnoma topilmadi",
                    "en": "Contract not found"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    if contract.status != ContractStatus.ACTIVE:
        return {
            "error": {
                "code": PaymeError.INVALID_ACCOUNT,
                "message": {
                    "ru": "Договор не активен. Оплата возможна только по активным договорам",
                    "uz": "Shartnoma faol emas. To'lov faqat faol shartnomalar bo'yicha mumkin",
                    "en": "Contract is not active. Payment is only possible for active contracts"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    student = contract.student

    # ✅ BOSQICH 1: Faqat contract (student ma'lumotlarini ko'rish)
    if not amount:
        print("📋 Step 1: Showing student info only")
        return create_success_response(
            {
                "allow": True,
                "additional": {
                    "name": f"{student.first_name} {student.last_name}",
                    "phone": student.phone or "",
                    "contract_status": contract.status.value,
                    "contract_number": contract.contract_number,
                    "monthly_fee": float(contract.monthly_fee),
                    "start_date": contract.start_date.isoformat(),
                    "end_date": contract.end_date.isoformat()
                }
            },
            request_id
        )

    # ✅ BOSQICH 2: To'liq ma'lumot (to'lovni tasdiqlash)
    print("💰 Step 2: Full payment validation")

    amount_sum = float(amount)
    expected_amount = float(contract.monthly_fee)

    if amount_sum != expected_amount:
        return {
            "error": {
                "code": PaymeError.INVALID_AMOUNT,
                "message": {
                    "ru": f"Сумма должна быть равна месячной оплате: {expected_amount}",
                    "uz": f"Summa oylik to'lovga teng bo'lishi kerak: {expected_amount}",
                    "en": f"Amount must equal monthly fee: {expected_amount}"
                }
            },
            "id": request_id
        }

    payment_year = account.get("payment_year")
    payment_month = account.get("payment_month")

    if payment_year is not None:
        try:
            payment_year = int(payment_year)
        except (TypeError, ValueError):
            return {
                "error": {
                    "code": PaymeError.INVALID_PARAMS,
                    "message": {
                        "ru": "Неверный год оплаты",
                        "uz": "Noto'g'ri to'lov yili",
                        "en": "Invalid payment year"
                    }
                },
                "id": request_id
            }
    else:
        payment_year = datetime.now().year

    if payment_month is not None:
        try:
            payment_month = int(payment_month)
        except (TypeError, ValueError):
            return {
                "error": {
                    "code": PaymeError.INVALID_PARAMS,
                    "message": {
                        "ru": "Неверный месяц оплаты",
                        "uz": "Noto'g'ri to'lov oyi",
                        "en": "Invalid payment month"
                    }
                },
                "id": request_id
            }
    else:
        payment_month = datetime.now().month

    if not (1 <= payment_month <= 12):
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверный месяц оплаты",
                    "uz": "Noto'g'ri to'lov oyi",
                    "en": "Invalid payment month"
                }
            },
            "id": request_id
        }

    from datetime import date as date_class
    payment_date = date_class(payment_year, payment_month, 1)
    contract_start_month = date_class(contract.start_date.year, contract.start_date.month, 1)
    contract_end_month = date_class(contract.end_date.year, contract.end_date.month, 1)

    if payment_date < contract_start_month:
        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": f"Договор еще не начался. Начало: {contract.start_date.isoformat()}",
                    "uz": f"Shartnoma hali boshlanmagan. Boshlanishi: {contract.start_date.isoformat()}",
                    "en": f"Contract has not started yet. Start date: {contract.start_date.isoformat()}"
                }
            },
            "id": request_id
        }

    if payment_date > contract_end_month:
        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": f"Договор истек. Окончание: {contract.end_date.isoformat()}",
                    "uz": f"Shartnoma muddati tugagan. Tugash sanasi: {contract.end_date.isoformat()}",
                    "en": f"Contract has expired. End date: {contract.end_date.isoformat()}"
                }
            },
            "id": request_id
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
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": f"Оплата за {month_names_ru[payment_month]} {payment_year} уже существует",
                    "uz": f"{month_names_uz[payment_month]} {payment_year} uchun to'lov allaqachon mavjud",
                    "en": f"Payment for {month_names_en[payment_month]} {payment_year} already exists"
                }
            },
            "id": request_id
        }

    # To'liq validatsiya o'tdi
    return create_success_response(
        {
            "allow": True,
            "additional": {
                "name": f"{student.first_name} {student.last_name}",
                "contract_status": contract.status.value,
                "contract_number": contract.contract_number,
                "monthly_fee": float(contract.monthly_fee)
            }
        },
        request_id
    )


async def create_transaction(params: dict, request_id: int, db: AsyncSession):
    payme_id = params.get("id")
    time = params.get("time")
    amount = params.get("amount")
    account = params.get("account", {})

    if not all([payme_id, time, amount, account]):
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверные параметры",
                    "uz": "Noto'g'ri parametrlar",
                    "en": "Invalid parameters"
                }
            },
            "id": request_id
        }

    contract_number = account.get("contract")
    if not contract_number:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Номер договора не указан",
                    "uz": "Shartnoma raqami ko'rsatilmagan",
                    "en": "Contract number not provided"
                }
            },
            "id": request_id
        }

    print(f"🔍 CreateTransaction: payme_id={payme_id}, contract={contract_number}")

    existing_result = await db.execute(
        select(Transaction).where(
            Transaction.external_id == str(payme_id)
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        print(f"✅ Transaction already exists: id={existing.id}, status={existing.status}")

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
            return create_success_response(
                {
                    "create_time": int(existing.created_at.timestamp() * 1000),
                    "perform_time": 0,
                    "cancel_time": int(existing.updated_at.timestamp() * 1000) if existing.updated_at else 0,
                    "transaction": str(existing.id),
                    "state": -2,
                    "reason": 5
                },
                request_id
            )

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

    contract_result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.student))
        .where(Contract.contract_number == contract_number)
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return {
            "error": {
                "code": -31050,
                "message": {
                    "ru": "Договор с таким номером не найден",
                    "uz": "Bunday raqamli shartnoma topilmadi",
                    "en": "Contract with this number not found"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    if contract.status != ContractStatus.ACTIVE:
        return {
            "error": {
                "code": -31051,
                "message": {
                    "ru": "Договор не активен",
                    "uz": "Shartnoma faol emas",
                    "en": "Contract is not active"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    amount_sum = float(amount)
    expected_amount = float(contract.monthly_fee)

    if amount_sum != expected_amount:
        return {
            "error": {
                "code": PaymeError.INVALID_AMOUNT,
                "message": {
                    "ru": f"Сумма оплаты должна быть ровно {expected_amount}",
                    "uz": f"To'lov summasi aynan {expected_amount} bo'lishi kerak",
                    "en": f"Payment amount must be exactly {expected_amount}"
                }
            },
            "id": request_id
        }

    payment_year = account.get("payment_year")
    payment_month = account.get("payment_month")

    if payment_year is not None:
        try:
            payment_year = int(payment_year)
        except (TypeError, ValueError):
            return {
                "error": {
                    "code": PaymeError.INVALID_PARAMS,
                    "message": {
                        "ru": "Неверный год оплаты",
                        "uz": "Noto'g'ri to'lov yili",
                        "en": "Invalid payment year"
                    }
                },
                "id": request_id
            }
    else:
        payment_year = datetime.now().year

    if payment_month is not None:
        try:
            payment_month = int(payment_month)
        except (TypeError, ValueError):
            return {
                "error": {
                    "code": PaymeError.INVALID_PARAMS,
                    "message": {
                        "ru": "Неверный месяц оплаты",
                        "uz": "Noto'g'ri to'lov oyi",
                        "en": "Invalid payment month"
                    }
                },
                "id": request_id
            }
    else:
        payment_month = datetime.now().month

    if not (1 <= payment_month <= 12):
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверный месяц оплаты",
                    "uz": "Noto'g'ri to'lov oyi",
                    "en": "Invalid payment month"
                }
            },
            "id": request_id
        }

    print(f"📅 Payment for: {payment_month}/{payment_year}")

    from datetime import date as date_class
    payment_date = date_class(payment_year, payment_month, 1)
    contract_start_month = date_class(contract.start_date.year, contract.start_date.month, 1)
    contract_end_month = date_class(contract.end_date.year, contract.end_date.month, 1)

    if payment_date < contract_start_month or payment_date > contract_end_month:
        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": "Договор истек или еще не начался",
                    "uz": "Shartnoma muddati tugagan yoki hali boshlanmagan",
                    "en": "Contract has expired or not started yet"
                }
            },
            "id": request_id
        }

    other_pending_result = await db.execute(
        select(Transaction).where(
            Transaction.contract_id == contract.id,
            Transaction.status == PaymentStatus.PENDING,
            Transaction.payment_year == payment_year,
            cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB)),
            Transaction.external_id != str(payme_id)
        )
    )
    other_pending_list = other_pending_result.scalars().all()

    if other_pending_list:
        print(f"⚠️ Found {len(other_pending_list)} other pending transactions")
        return {
            "error": {
                "code": -31050,
                "message": {
                    "ru": "Для данного договора уже существует активная транзакция ожидания оплаты",
                    "uz": "Ushbu shartnoma uchun to'lov kutilayotgan faol tranzaksiya mavjud",
                    "en": "An active pending transaction already exists for this contract"
                },
                "data": "account.contract"
            },
            "id": request_id
        }

    success_result = await db.execute(
        select(Transaction).where(
            Transaction.contract_id == contract.id,
            Transaction.status == PaymentStatus.SUCCESS,
            Transaction.payment_year == payment_year,
            cast(Transaction.payment_months, JSONB).op('@>')(cast([payment_month], JSONB))
        )
    )
    success_payment = success_result.scalar_one_or_none()

    if success_payment:
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
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": f"Оплата за {month_names_ru[payment_month]} {payment_year} уже существует",
                    "uz": f"{month_names_uz[payment_month]} {payment_year} uchun to'lov allaqachon mavjud",
                    "en": f"Payment for {month_names_en[payment_month]} {payment_year} already exists"
                }
            },
            "id": request_id
        }

    transaction = Transaction(
        external_id=str(payme_id),
        amount=amount_sum,
        source=PaymentSource.PAYME,
        status=PaymentStatus.PENDING,
        contract_id=contract.id,
        student_id=contract.student_id,
        payment_year=payment_year,
        payment_months=[payment_month],
        comment=f"Payme create: ID {payme_id}, month {payment_month}/{payment_year}"
    )

    db.add(transaction)

    try:
        await db.commit()
        await db.refresh(transaction)
        print(f"✅ Transaction created: id={transaction.id}, external_id={transaction.external_id}")
    except Exception as e:
        await db.rollback()
        print(f"❌ Error creating transaction: {e}")
        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": "Ошибка создания транзакции",
                    "uz": "Tranzaksiya yaratishda xatolik",
                    "en": "Error creating transaction"
                }
            },
            "id": request_id
        }

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
    payme_id = params.get("id")

    if not payme_id:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверные параметры",
                    "uz": "Noto'g'ri parametrlar",
                    "en": "Invalid parameters"
                }
            },
            "id": request_id
        }

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.external_id == str(payme_id)
        )
    )
    transaction = transaction_result.scalar_one_or_none()

    if not transaction:
        return {
            "error": {
                "code": PaymeError.TRANSACTION_NOT_FOUND,
                "message": {
                    "ru": "Транзакция не найдена",
                    "uz": "Tranzaksiya topilmadi",
                    "en": "Transaction not found"
                }
            },
            "id": request_id
        }

    # ✅ Debug: Status ni ko'rish
    print(f"🔍 PerformTransaction: id={payme_id}, status={transaction.status}, paid_at={transaction.paid_at}")

    # ✅ SUCCESS - Idempotent
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

    # ✅ CANCELLED - Xato qaytarish (har ikkala holat uchun: -1 va -2)
    if transaction.status == PaymentStatus.CANCELLED:
        # Debug: Qaysi state bo'lganini ko'rish
        state = -2 if transaction.paid_at else -1
        print(f"❌ Cannot perform: Transaction is CANCELLED with state {state}")

        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,  # -31008
                "message": {
                    "ru": "Транзакция отменена",
                    "uz": "Tranzaksiya bekor qilingan",
                    "en": "Transaction cancelled"
                }
            },
            "id": request_id
        }

    # ✅ PENDING - Perform qilish
    contract_result = await db.execute(
        select(Contract).where(Contract.id == transaction.contract_id)
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": "Договор не найден",
                    "uz": "Shartnoma topilmadi",
                    "en": "Contract not found"
                }
            },
            "id": request_id
        }

    if contract.status != ContractStatus.ACTIVE:
        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": "Договор не активен",
                    "uz": "Shartnoma faol emas",
                    "en": "Contract is not active"
                }
            },
            "id": request_id
        }

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

        return {
            "error": {
                "code": PaymeError.COULD_NOT_PERFORM,
                "message": {
                    "ru": "Оплата за этот месяц уже существует",
                    "uz": "Ushbu oy uchun to'lov allaqachon mavjud",
                    "en": "Payment for this month already exists"
                }
            },
            "id": request_id
        }

    # ✅ PENDING → SUCCESS
    transaction.status = PaymentStatus.SUCCESS
    transaction.paid_at = datetime.utcnow()
    transaction.comment = f"Payme confirmed: ID {payme_id}, month {payment_month}/{payment_year}"

    await db.commit()
    await db.refresh(transaction)

    print(f"✅ Transaction performed: id={transaction.id}, state=2")

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
    payme_id = params.get("id")

    if not payme_id:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверные параметры",
                    "uz": "Noto'g'ri parametrlar",
                    "en": "Invalid parameters"
                }
            },
            "id": request_id
        }

    transaction_result = await db.execute(
        select(Transaction).where(
            (Transaction.external_id == str(payme_id)) |
            (cast(Transaction.id, String) == str(payme_id))
        )
    )

    transaction = transaction_result.scalar_one_or_none()

    if not transaction:
        return {
            "error": {
                "code": PaymeError.TRANSACTION_NOT_FOUND,
                "message": {
                    "ru": "Транзакция не найдена",
                    "uz": "Tranzaksiya topilmadi",
                    "en": "Transaction not found"
                }
            },
            "id": request_id
        }

    # SUCCESS
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

    # ✅ CANCELLED
    if transaction.status == PaymentStatus.CANCELLED:
        state = -2 if transaction.paid_at else -1
        perform_time = int(transaction.paid_at.timestamp() * 1000) if transaction.paid_at else 0

        # ✅ Reason ni comment dan olish
        reason = None
        if transaction.comment and "reason" in transaction.comment.lower():
            try:
                reason = int(transaction.comment.split("reason")[-1].strip())
            except:
                pass  # Agar parse qilib bo'lmasa, None qoladi

        print(f"🔍 CheckTransaction: state={state}, perform_time={perform_time}, reason={reason}")

        return create_success_response(
            {
                "create_time": int(transaction.created_at.timestamp() * 1000),
                "perform_time": perform_time,  # ✅ paid_at ga qarab 0 yoki timestamp
                "cancel_time": int(transaction.updated_at.timestamp() * 1000) if transaction.updated_at else 0,
                "transaction": str(transaction.id),
                "state": state,  # ✅ paid_at ga qarab -1 yoki -2
                "reason": reason  # ✅ Comment dan olingan
            },
            request_id
        )

    # PENDING
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
    payme_id = params.get("id")
    reason = params.get("reason", 5)

    if not payme_id:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверные параметры",
                    "uz": "Noto'g'ri parametrlar",
                    "en": "Invalid parameters"
                }
            },
            "id": request_id
        }

    transaction_result = await db.execute(
        select(Transaction).where(
            Transaction.external_id == str(payme_id)
        )
    )
    transaction = transaction_result.scalar_one_or_none()

    if not transaction:
        return {
            "error": {
                "code": PaymeError.TRANSACTION_NOT_FOUND,
                "message": {
                    "ru": "Транзакция не найдена",
                    "uz": "Tranzaksiya topilmadi",
                    "en": "Transaction not found"
                }
            },
            "id": request_id
        }

    # Agar allaqachon bekor qilingan bo'lsa
    if transaction.status == PaymentStatus.CANCELLED:
        state = -2 if transaction.paid_at else -1
        perform_time = int(transaction.paid_at.timestamp() * 1000) if transaction.paid_at else 0
        cancel_time = int(transaction.updated_at.timestamp() * 1000) if transaction.updated_at else int(
            datetime.utcnow().timestamp() * 1000)

        saved_reason = reason
        if transaction.comment and "reason" in transaction.comment.lower():
            try:
                saved_reason = int(transaction.comment.split("reason")[-1].strip())
            except:
                saved_reason = reason

        return create_success_response(
            {
                "create_time": int(transaction.created_at.timestamp() * 1000),
                "perform_time": perform_time,
                "cancel_time": cancel_time,
                "transaction": str(transaction.id),
                "state": state,
                "reason": saved_reason
            },
            request_id
        )

    # State aniqlash
    state = -2 if transaction.paid_at else -1
    perform_time = int(transaction.paid_at.timestamp() * 1000) if transaction.paid_at else 0

    # Bekor qilish
    transaction.status = PaymentStatus.CANCELLED
    transaction.comment = f"Cancelled by Payme: reason {reason}"

    # ✅ Hozirgi vaqtni olish (cancel_time uchun)
    cancel_time_ms = int(datetime.utcnow().timestamp() * 1000)

    await db.commit()

    return create_success_response(
        {
            "create_time": int(transaction.created_at.timestamp() * 1000),
            "perform_time": perform_time,
            "cancel_time": cancel_time_ms,  # ✅ Hozirgi vaqt
            "transaction": str(transaction.id),
            "state": state,
            "reason": reason
        },
        request_id
    )



async def get_statement(params: dict, request_id: int, db: AsyncSession):
    """
    Payme hisobotlari uchun tranzaksiyalar ro'yxatini qaytarish

    Talablar:
    1. from <= created_at <= to
    2. Faqat CreateTransaction orqali yaratilgan tranzaksiyalar
    3. created_at bo'yicha o'sish tartibida saralash
    """
    from_time = params.get("from")
    to_time = params.get("to")

    if from_time is None or to_time is None:
        return {
            "error": {
                "code": PaymeError.INVALID_PARAMS,
                "message": {
                    "ru": "Неверные параметры",
                    "uz": "Noto'g'ri parametrlar",
                    "en": "Invalid parameters"
                }
            },
            "id": request_id
        }

    # Timestamp'larni datetime ga o'tkazish (milliseconds)
    from datetime import datetime as dt
    from_datetime = dt.fromtimestamp(from_time / 1000.0)
    to_datetime = dt.fromtimestamp(to_time / 1000.0)

    print(f"📊 GetStatement: from {from_datetime} to {to_datetime}")

    # Tranzaksiyalarni olish
    transactions_result = await db.execute(
        select(Transaction)
        .where(
            Transaction.source == PaymentSource.PAYME,
            Transaction.created_at >= from_datetime,
            Transaction.created_at <= to_datetime
        )
        .order_by(Transaction.created_at.asc())  # O'sish tartibida
    )
    transactions = transactions_result.scalars().all()

    print(f"✅ Found {len(transactions)} transactions")

    # Javobni tayyorlash
    transactions_list = []

    for trans in transactions:
        # Contract ma'lumotlarini olish
        contract_result = await db.execute(
            select(Contract).where(Contract.id == trans.contract_id)
        )
        contract = contract_result.scalar_one_or_none()

        # State aniqlash
        if trans.status == PaymentStatus.SUCCESS:
            state = 2
        elif trans.status == PaymentStatus.CANCELLED:
            state = -2
        else:
            state = 1

        # Perform time
        perform_time = 0
        if trans.paid_at:
            perform_time = int(trans.paid_at.timestamp() * 1000)

        # Cancel time
        cancel_time = 0
        if trans.status == PaymentStatus.CANCELLED and trans.updated_at:
            cancel_time = int(trans.updated_at.timestamp() * 1000)

        # Reason
        reason = None
        if trans.status == PaymentStatus.CANCELLED:
            reason = 5  # Cancelled by timeout or user

        transactions_list.append({
            "id": trans.external_id,  # Payme ID
            "time": int(trans.created_at.timestamp() * 1000),  # Create time in Payme
            "amount": int(trans.amount),
            "account": {
                "contract": contract.contract_number if contract else "",
                "payment_year": trans.payment_year,
                "payment_month": trans.payment_months[0] if trans.payment_months else None
            },
            "create_time": int(trans.created_at.timestamp() * 1000),
            "perform_time": perform_time,
            "cancel_time": cancel_time,
            "transaction": str(trans.id),  # Bizning ID
            "state": state,
            "reason": reason
        })

    return create_success_response(
        {
            "transactions": transactions_list
        },
        request_id
    )


