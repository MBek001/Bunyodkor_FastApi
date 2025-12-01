from typing import Annotated, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.core.db import get_db
from app.core.permissions import (
    PERM_FINANCE_TRANSACTIONS_VIEW,
    PERM_FINANCE_UNASSIGNED_VIEW,
    PERM_FINANCE_TRANSACTIONS_MANUAL,
    PERM_FINANCE_UNASSIGNED_ASSIGN,
    PERM_FINANCE_TRANSACTIONS_CANCEL,
)
from app.models.finance import Transaction
from app.models.enums import PaymentStatus
from app.schemas.transaction import TransactionRead, ManualTransactionCreate, TransactionAssign
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission, CurrentUser
from app.services.payment import create_manual_transaction, assign_transaction, cancel_transaction

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_model=DataResponse[list[TransactionRead]], dependencies=[Depends(require_permission(PERM_FINANCE_TRANSACTIONS_VIEW))])
async def get_transactions(
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    student_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Transaction)
    conditions = []

    if from_date:
        conditions.append(Transaction.created_at >= from_date)
    if to_date:
        conditions.append(Transaction.created_at <= to_date)
    if status:
        conditions.append(Transaction.status == status)
    if source:
        conditions.append(Transaction.source == source)
    if student_id:
        conditions.append(Transaction.student_id == student_id)

    if conditions:
        query = query.where(and_(*conditions))

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    transactions = result.scalars().all()

    count_query = select(func.count(Transaction.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return DataResponse(
        data=[TransactionRead.model_validate(t) for t in transactions],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/unassigned", response_model=DataResponse[list[TransactionRead]], dependencies=[Depends(require_permission(PERM_FINANCE_UNASSIGNED_VIEW))])
async def get_unassigned_transactions(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Transaction)
        .where(Transaction.status == PaymentStatus.UNASSIGNED)
        .offset(offset)
        .limit(page_size)
    )
    transactions = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Transaction.id)).where(Transaction.status == PaymentStatus.UNASSIGNED)
    )
    total = count_result.scalar()

    return DataResponse(
        data=[TransactionRead.model_validate(t) for t in transactions],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/{transaction_id}", response_model=DataResponse[TransactionRead], dependencies=[Depends(require_permission(PERM_FINANCE_TRANSACTIONS_VIEW))])
async def get_transaction(
    transaction_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return DataResponse(data=TransactionRead.model_validate(transaction))


@router.post("/manual", response_model=DataResponse[TransactionRead], dependencies=[Depends(require_permission(PERM_FINANCE_TRANSACTIONS_MANUAL))])
async def create_manual_transaction_endpoint(
    data: ManualTransactionCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    transaction = await create_manual_transaction(db, data, user.id)
    return DataResponse(data=TransactionRead.model_validate(transaction))


@router.patch("/{transaction_id}/assign", response_model=DataResponse[TransactionRead], dependencies=[Depends(require_permission(PERM_FINANCE_UNASSIGNED_ASSIGN))])
async def assign_transaction_endpoint(
    transaction_id: int,
    data: TransactionAssign,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        transaction = await assign_transaction(db, transaction_id, data.student_id, data.contract_id)
        return DataResponse(data=TransactionRead.model_validate(transaction))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{transaction_id}/cancel", response_model=DataResponse[TransactionRead], dependencies=[Depends(require_permission(PERM_FINANCE_TRANSACTIONS_CANCEL))])
async def cancel_transaction_endpoint(
    transaction_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        transaction = await cancel_transaction(db, transaction_id)
        return DataResponse(data=TransactionRead.model_validate(transaction))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{transaction_id}", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_FINANCE_TRANSACTIONS_CANCEL))])
async def delete_transaction(
    transaction_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    await db.delete(transaction)
    await db.commit()

    return DataResponse(data={"message": "Transaction deleted successfully"})
