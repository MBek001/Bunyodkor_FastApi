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
