from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.domain import Student, Contract
from app.models.finance import Transaction
from app.models.enums import ContractStatus, PaymentStatus


async def calculate_student_debt(db: AsyncSession, student_id: int, as_of_date: date = None) -> float:
    if as_of_date is None:
        as_of_date = date.today()

    result = await db.execute(
        select(Contract).where(
            and_(
                Contract.student_id == student_id,
                Contract.status == ContractStatus.ACTIVE,
                Contract.start_date <= as_of_date,
                Contract.end_date >= as_of_date,
            )
        )
    )
    contract = result.scalar_one_or_none()

    if not contract:
        return 0.0

    months_elapsed = 0
    current_date = contract.start_date
    while current_date <= as_of_date and current_date <= contract.end_date:
        months_elapsed += 1
        current_date = current_date + relativedelta(months=1)

    total_expected = float(contract.monthly_fee) * months_elapsed

    txn_result = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.contract_id == contract.id,
                Transaction.status == PaymentStatus.SUCCESS,
            )
        )
    )
    transactions = txn_result.scalars().all()
    total_paid = sum(float(txn.amount) for txn in transactions)

    debt = total_expected - total_paid
    return max(debt, 0.0)


async def check_current_month_payment(db: AsyncSession, student_id: int) -> bool:
    today = date.today()
    first_day_of_month = today.replace(day=1)

    result = await db.execute(
        select(Contract).where(
            and_(
                Contract.student_id == student_id,
                Contract.status == ContractStatus.ACTIVE,
                Contract.start_date <= today,
                Contract.end_date >= today,
            )
        )
    )
    contract = result.scalar_one_or_none()

    if not contract:
        return False

    txn_result = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.contract_id == contract.id,
                Transaction.status == PaymentStatus.SUCCESS,
                Transaction.paid_at >= first_day_of_month,
            )
        )
    )
    transactions = txn_result.scalars().all()

    total_paid_this_month = sum(float(txn.amount) for txn in transactions)
    return total_paid_this_month >= float(contract.monthly_fee)
