from datetime import datetime
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
    if data.student_id:
        from app.models.domain import Student
        student_result = await db.execute(select(Student).where(Student.id == data.student_id))
        if not student_result.scalar_one_or_none():
            raise ValueError(f"Student with ID {data.student_id} not found")

    if data.contract_id:
        contract_result = await db.execute(select(Contract).where(Contract.id == data.contract_id))
        if not contract_result.scalar_one_or_none():
            raise ValueError(f"Contract with ID {data.contract_id} not found")

    transaction = Transaction(
        amount=data.amount,
        source=data.source,
        status=PaymentStatus.SUCCESS,
        student_id=data.student_id,
        contract_id=data.contract_id,
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
