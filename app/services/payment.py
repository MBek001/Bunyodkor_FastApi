from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.finance import Transaction
from app.models.domain import Contract
from app.models.enums import PaymentStatus, PaymentSource
from app.schemas.transaction import ManualTransactionCreate


async def create_manual_transaction(
    db: AsyncSession,
    data: ManualTransactionCreate,
    user_id: int,
) -> Transaction:
    # Find contract by contract_number
    contract_result = await db.execute(
        select(Contract).where(Contract.contract_number == data.contract_number)
    )
    contract = contract_result.scalar_one_or_none()

    if not contract:
        raise ValueError(f"Contract with number '{data.contract_number}' not found")

    # Validate payment months
    if not data.payment_months:
        raise ValueError("Payment months are required")

    for month in data.payment_months:
        if month < 1 or month > 12:
            raise ValueError(f"Invalid month: {month}. Must be between 1 and 12")

    # Determine the effective end date (earliest of end_date or terminated_at)
    effective_end_date = contract.end_date
    if contract.terminated_at:
        termination_date = contract.terminated_at.date()
        if termination_date < effective_end_date:
            effective_end_date = termination_date

    # Validate that payment months fall within contract period
    for month in data.payment_months:
        # Create date for the first day of the payment month
        payment_date = date(data.payment_year, month, 1)

        # Check if payment month is before contract start
        contract_start_month = contract.start_date.replace(day=1)
        if payment_date < contract_start_month:
            raise ValueError(
                f"Payment for {payment_date.strftime('%B %Y')} is before contract start date "
                f"({contract.start_date}). Contract period: {contract.start_date} to {effective_end_date}"
            )

        # Check if payment month is after contract end/termination
        contract_end_month = effective_end_date.replace(day=1)
        if payment_date > contract_end_month:
            termination_msg = " (terminated)" if contract.terminated_at else ""
            raise ValueError(
                f"Payment for {payment_date.strftime('%B %Y')} is after contract end date "
                f"({effective_end_date}){termination_msg}. Contract period: {contract.start_date} to {effective_end_date}"
            )

    transaction = Transaction(
        amount=data.amount,
        source=data.source,
        status=PaymentStatus.SUCCESS,
        student_id=contract.student_id,
        contract_id=contract.id,
        payment_year=data.payment_year,
        payment_months=data.payment_months,
        comment=data.comment,
        paid_at=data.paid_at or datetime.utcnow(),
        created_by_user_id=user_id,
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction


async def assign_transaction(
    db: AsyncSession,
    transaction_id: int,
    student_id: int,
    contract_id: int,
) -> Transaction:
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise ValueError("Transaction not found")

    if transaction.status != PaymentStatus.UNASSIGNED:
        raise ValueError("Transaction is not unassigned")

    from app.models.domain import Student
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    if not student_result.scalar_one_or_none():
        raise ValueError(f"Student with ID {student_id} not found")

    contract_result = await db.execute(select(Contract).where(Contract.id == contract_id))
    if not contract_result.scalar_one_or_none():
        raise ValueError(f"Contract with ID {contract_id} not found")

    transaction.student_id = student_id
    transaction.contract_id = contract_id
    transaction.status = PaymentStatus.SUCCESS
    if not transaction.paid_at:
        transaction.paid_at = datetime.utcnow()

    await db.commit()
    await db.refresh(transaction)
    return transaction


async def cancel_transaction(db: AsyncSession, transaction_id: int) -> Transaction:
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise ValueError("Transaction not found")

    transaction.status = PaymentStatus.CANCELLED
    await db.commit()
    await db.refresh(transaction)
    return transaction
