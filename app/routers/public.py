from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.db import get_db
from app.models.domain import Contract, Student
from app.models.finance import Transaction
from app.models.enums import PaymentStatus
from app.schemas.public import PublicContractInfo, PublicPaymentInitiate
from app.services.debt import calculate_student_debt

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/contracts/{contract_number}", response_model=PublicContractInfo)
async def get_contract_info(
    contract_number: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Contract).where(Contract.contract_number == contract_number))
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    student_result = await db.execute(select(Student).where(Student.id == contract.student_id))
    student = student_result.scalar_one()

    debt = await calculate_student_debt(db, student.id)

    last_payment_result = await db.execute(
        select(Transaction.paid_at)
        .where(Transaction.contract_id == contract.id, Transaction.status == PaymentStatus.SUCCESS)
        .order_by(Transaction.paid_at.desc())
    )
    last_payment = last_payment_result.scalar_one_or_none()

    return PublicContractInfo(
        contract_number=contract.contract_number,
        student_first_name=student.first_name,
        student_last_name=student.last_name,
        monthly_fee=float(contract.monthly_fee),
        start_date=contract.start_date,
        end_date=contract.end_date,
        current_debt=debt,
        last_payment_date=last_payment.date() if last_payment else None,
    )


@router.post("/payments/payme")
async def initiate_payme_payment(data: PublicPaymentInitiate):
    return {"message": "Payme integration placeholder", "data": data}


@router.post("/payments/click")
async def initiate_click_payment(data: PublicPaymentInitiate):
    return {"message": "Click integration placeholder", "data": data}


@router.post("/payments/callback/payme")
async def payme_callback(payload: dict):
    return {"message": "Payme callback placeholder", "payload": payload}


@router.post("/payments/callback/click")
async def click_callback(payload: dict):
    return {"message": "Click callback placeholder", "payload": payload}
