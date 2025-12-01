from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.db import get_db
from app.core.permissions import PERM_CONTRACTS_VIEW, PERM_CONTRACTS_EDIT
from app.models.domain import Contract
from app.schemas.contract import ContractRead, ContractCreate, ContractUpdate
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission

router = APIRouter(prefix="/contracts", tags=["Contracts"])


@router.get("", response_model=DataResponse[list[ContractRead]], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_contracts(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = None,
    student_id: Optional[int] = None,
    contract_number: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Contract)

    if status:
        query = query.where(Contract.status == status)
    if student_id:
        query = query.where(Contract.student_id == student_id)
    if contract_number:
        query = query.where(Contract.contract_number.ilike(f"%{contract_number}%"))

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    contracts = result.scalars().all()

    count_query = select(func.count(Contract.id))
    if status:
        count_query = count_query.where(Contract.status == status)
    if student_id:
        count_query = count_query.where(Contract.student_id == student_id)
    if contract_number:
        count_query = count_query.where(Contract.contract_number.ilike(f"%{contract_number}%"))

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return DataResponse(
        data=[ContractRead.model_validate(c) for c in contracts],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.post("", response_model=DataResponse[ContractRead], dependencies=[Depends(require_permission(PERM_CONTRACTS_EDIT))])
async def create_contract(
    data: ContractCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.domain import Student
    from app.models.enums import ContractStatus

    # Check if student exists
    student_result = await db.execute(select(Student).where(Student.id == data.student_id))
    if not student_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Student with ID {data.student_id} not found")

    # Check for duplicate contract number
    existing_contract = await db.execute(
        select(Contract).where(Contract.contract_number == data.contract_number)
    )
    if existing_contract.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="This contract already exists")

    # Check if student already has an active contract
    active_contract = await db.execute(
        select(Contract).where(
            Contract.student_id == data.student_id,
            Contract.status == ContractStatus.ACTIVE
        )
    )
    if active_contract.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="This student already has an active contract. A student can only have one active contract at a time"
        )

    contract = Contract(**data.model_dump())
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    return DataResponse(data=ContractRead.model_validate(contract))


@router.get("/{contract_id}", response_model=DataResponse[ContractRead], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_contract(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    return DataResponse(data=ContractRead.model_validate(contract))


@router.patch("/{contract_id}", response_model=DataResponse[ContractRead], dependencies=[Depends(require_permission(PERM_CONTRACTS_EDIT))])
async def update_contract(
    contract_id: int,
    data: ContractUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.enums import ContractStatus

    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    update_data = data.model_dump(exclude_unset=True)

    # Check for duplicate contract number if it's being updated
    if "contract_number" in update_data:
        existing_contract = await db.execute(
            select(Contract).where(
                Contract.contract_number == update_data["contract_number"],
                Contract.id != contract_id
            )
        )
        if existing_contract.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="This contract already exists")

    # Check if student already has an active contract (when changing status to ACTIVE or changing student)
    if "status" in update_data and update_data["status"] == ContractStatus.ACTIVE:
        active_contract = await db.execute(
            select(Contract).where(
                Contract.student_id == contract.student_id,
                Contract.status == ContractStatus.ACTIVE,
                Contract.id != contract_id
            )
        )
        if active_contract.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="This student already has an active contract. A student can only have one active contract at a time"
            )

    if "student_id" in update_data and update_data["student_id"] != contract.student_id:
        # Check if the new student already has an active contract (only if this contract is active)
        if contract.status == ContractStatus.ACTIVE:
            active_contract = await db.execute(
                select(Contract).where(
                    Contract.student_id == update_data["student_id"],
                    Contract.status == ContractStatus.ACTIVE
                )
            )
            if active_contract.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="The target student already has an active contract. A student can only have one active contract at a time"
                )

    for field, value in update_data.items():
        setattr(contract, field, value)

    await db.commit()
    await db.refresh(contract)
    return DataResponse(data=ContractRead.model_validate(contract))


@router.delete("/{contract_id}", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_CONTRACTS_EDIT))])
async def delete_contract(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    await db.delete(contract)
    await db.commit()

    return DataResponse(data={"message": "Contract deleted successfully"})
