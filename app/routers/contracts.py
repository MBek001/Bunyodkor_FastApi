from typing import Annotated, Optional, List
from datetime import datetime
import json
import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from app.core.db import get_db
from app.core.permissions import PERM_CONTRACTS_VIEW, PERM_CONTRACTS_EDIT
from app.core.s3 import upload_image_to_s3
from app.models.domain import Contract, Student, Group, WaitingList
from app.schemas.contract import (
    ContractRead, ContractUpdate, ContractTerminate,
    ContractCreateWithDocuments, ContractCreatedResponse,
    ContractNumberInfo, NextAvailableNumber, ContractCustomFields
)
from app.schemas.common import DataResponse, PaginationMeta
from app.deps import require_permission, CurrentUser
from app.models.auth import User
from app.models.enums import ContractStatus
from app.services.contract_allocation import (
    allocate_contract_number,
    get_available_contract_numbers,
    get_next_available_sequence,
    is_group_full,
    ContractNumberAllocationError
)
# from app.utils.pdf_generator import ContractGenerator, convert_dates

router = APIRouter(prefix="/contracts", tags=["Contracts"])


@router.get("", response_model=DataResponse[list[ContractRead]], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_contracts(
    db: Annotated[AsyncSession, Depends(get_db)],
    archive_year: int | None = Query(None, description="Filter by archive year (defaults to current year)"),
    include_archived: bool = Query(False, description="Include archived contracts (default: excludes ARCHIVED)"),
    status: Optional[str] = None,
    student_id: Optional[int] = None,
    contract_number: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get all contracts with optional filters.

    Default behavior:
    - Shows current year's contracts only
    - Shows only ACTIVE and EXPIRED contracts (excludes ARCHIVED and TERMINATED)
    - Set include_archived=true to also show ARCHIVED contracts
    - TERMINATED contracts are only visible via /archive/terminated-contracts endpoint
    """
    # Default to current year if not specified
    if archive_year is None:
        archive_year = datetime.now().year

    query = select(Contract).where(Contract.archive_year == archive_year)

    # Apply status filtering based on parameters
    if status:
        # If specific status requested, use it
        query = query.where(Contract.status == status)
    elif not include_archived:
        # Default: show only ACTIVE and EXPIRED (exclude ARCHIVED and TERMINATED)
        query = query.where(Contract.status.in_([ContractStatus.ACTIVE, ContractStatus.EXPIRED]))
    else:
        # include_archived=true: show ACTIVE, EXPIRED, and ARCHIVED (but not TERMINATED)
        query = query.where(Contract.status.in_([
            ContractStatus.ACTIVE,
            ContractStatus.EXPIRED,
            ContractStatus.ARCHIVED
        ]))
    if student_id:
        query = query.where(Contract.student_id == student_id)
    if contract_number:
        query = query.where(Contract.contract_number.ilike(f"%{contract_number}%"))

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    contracts = result.scalars().all()

    count_query = select(func.count(Contract.id)).where(Contract.archive_year == archive_year)

    # Apply same status filtering to count
    if status:
        count_query = count_query.where(Contract.status == status)
    elif not include_archived:
        count_query = count_query.where(Contract.status.in_([ContractStatus.ACTIVE, ContractStatus.EXPIRED]))
    else:
        count_query = count_query.where(Contract.status.in_([
            ContractStatus.ACTIVE,
            ContractStatus.EXPIRED,
            ContractStatus.ARCHIVED
        ]))
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


@router.get("/{contract_id}", response_model=DataResponse[ContractRead], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_contract(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.terminated_by))
        .where(Contract.id == contract_id)
    )
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


@router.post("/{contract_id}/terminate", response_model=DataResponse[ContractRead])
async def terminate_contract(
    contract_id: int,
    data: ContractTerminate,
    user: Annotated[User, Depends(require_permission(PERM_CONTRACTS_EDIT))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Terminate a contract with reason and termination date.
    Automatically changes contract status to TERMINATED.
    Records who terminated the contract with their full name.
    """
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.terminated_at:
        raise HTTPException(status_code=400, detail="Contract is already terminated")

    # Set termination details
    contract.terminated_at = data.terminated_at or datetime.utcnow()
    contract.terminated_by_user_id = user.id
    contract.termination_reason = data.termination_reason
    contract.status = ContractStatus.TERMINATED

    await db.commit()

    # Refresh with terminated_by relationship
    await db.refresh(contract, ["terminated_by"])

    return DataResponse(data=ContractRead.model_validate(contract))


@router.get("/payment-months/{contract_number}", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_contract_payment_months(
    contract_number: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get valid payment months for a contract based on start date and end/termination date.

    Uses contract_number instead of contract_id.

    Payment months are calculated:
    - Starting from the month of contract start_date
    - Ending at the month of contract end_date or terminated_at (whichever is earlier)
    - Only includes months within the contract period
    """
    result = await db.execute(select(Contract).where(Contract.contract_number == contract_number))
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_number}' not found")

    # Determine the effective end date (earliest of end_date or terminated_at)
    effective_end_date = contract.end_date
    if contract.terminated_at:
        termination_date = contract.terminated_at.date()
        if termination_date < effective_end_date:
            effective_end_date = termination_date

    # Generate list of valid payment months
    payment_months = []
    current_date = contract.start_date.replace(day=1)  # Start from first day of start month

    while current_date <= effective_end_date:
        payment_months.append({
            "year": current_date.year,
            "month": current_date.month,
            "month_name": current_date.strftime("%B"),
            "display": current_date.strftime("%B %Y")
        })

        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)

    return DataResponse(data={
        "contract_id": contract.id,
        "contract_number": contract.contract_number,
        "start_date": str(contract.start_date),
        "end_date": str(contract.end_date),
        "terminated_at": str(contract.terminated_at.date()) if contract.terminated_at else None,
        "effective_end_date": str(effective_end_date),
        "payment_months": payment_months,
        "total_months": len(payment_months)
    })


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


@router.post("/bulk-delete", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_CONTRACTS_EDIT))])
async def bulk_delete_contracts(
    contract_ids: list[int],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Bulk delete multiple contracts by their IDs"""
    if not contract_ids:
        raise HTTPException(status_code=400, detail="No contract IDs provided")

    deleted_count = 0
    errors = []

    for contract_id in contract_ids:
        try:
            result = await db.execute(select(Contract).where(Contract.id == contract_id))
            contract = result.scalar_one_or_none()

            if not contract:
                errors.append({"contract_id": contract_id, "error": "Contract not found"})
                continue

            await db.delete(contract)
            deleted_count += 1
        except Exception as e:
            errors.append({"contract_id": contract_id, "error": str(e)})

    await db.commit()

    return DataResponse(data={
        "message": f"Deleted {deleted_count} contract(s)",
        "deleted_count": deleted_count,
        "total_requested": len(contract_ids),
        "errors": errors if errors else None
    })



@router.post("/create-with-files", response_class=FileResponse, deprecated=True)
async def create_contract_with_file_upload(
    user: Annotated[User, Depends(require_permission(PERM_CONTRACTS_EDIT))],
    db: Annotated[AsyncSession, Depends(get_db)],
    student_id: int = Form(...),
    group_id: int = Form(...),
    contract_number: str = Form(...),
    custom_fields_json: str = Form(...),
    passport_copy: UploadFile = File(...),
    form_086: UploadFile = File(...),
    heart_checkup: UploadFile = File(...),
    birth_certificate: UploadFile = File(...),
    contract_images: List[UploadFile] = File(...)
):
    """
    ⚠️ DEPRECATED: This endpoint is deprecated and disabled.

    Please use POST /students/create-with-contract instead.

    The new endpoint:
    - Creates both student AND contract in one operation
    - Has all form fields visible (not hidden in JSON)
    - Uploads files to S3 automatically
    - Generates and returns PDF contract
    """
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Please use POST /students/create-with-contract instead."
    )
    # Parse custom fields
    try:
        custom_fields_dict = json.loads(custom_fields_json)
        custom_fields = ContractCustomFields(**custom_fields_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid custom_fields JSON: {e}")

    # Validate student
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student ID {student_id} not found")

    # Check for active contract
    active_contract = await db.execute(
        select(Contract).where(
            Contract.student_id == student_id,
            Contract.status == ContractStatus.ACTIVE
        )
    )
    if active_contract.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Student already has active contract")

    # Group check
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail=f"Group ID {group_id} not found")

    birth_year = custom_fields.student.birth_year

    # Check for duplicate contract number
    existing_contract = await db.execute(
        select(Contract).where(Contract.contract_number == contract_number)
    )
    if existing_contract.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Contract number already exists")

    # Parse contract number to get sequence
    if contract_number.startswith("N") and contract_number.endswith(str(birth_year)):
        seq_str = contract_number[1:-len(str(birth_year))]
        try:
            sequence_number = int(seq_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid contract number format")
    else:
        raise HTTPException(status_code=400, detail="Invalid contract number format (must be N{seq}{year})")

    # Upload images to S3
    try:
        passport_url = upload_image_to_s3(passport_copy, folder="contracts/passports")
        form_086_url = upload_image_to_s3(form_086, folder="contracts/medical")
        heart_url = upload_image_to_s3(heart_checkup, folder="contracts/medical")
        birth_cert_url = upload_image_to_s3(birth_certificate, folder="contracts/birth_certificates")
        contract_image_urls = [upload_image_to_s3(img, folder="contracts/pages") for img in contract_images]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload files to S3: {e}")

    # Create contract
    contract = Contract(
        contract_number=contract_number,
        birth_year=birth_year,
        sequence_number=sequence_number,
        start_date=custom_fields.contract_terms.contract_start_date,
        end_date=custom_fields.contract_terms.contract_end_date,
        monthly_fee=custom_fields.contract_terms.monthly_fee,
        status=ContractStatus.ACTIVE,
        student_id=student_id,
        group_id=group_id,
        passport_copy_url=passport_url,
        form_086_url=form_086_url,
        heart_checkup_url=heart_url,
        birth_certificate_url=birth_cert_url,
        contract_images_urls=json.dumps(contract_image_urls),
        custom_fields=json.dumps(custom_fields.model_dump(), ensure_ascii=False, default=str),
        signature_token=str(uuid.uuid4())
    )

    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    # Generate PDF
    try:
        # Create temporary directory if not exists
        os.makedirs("temp_pdfs", exist_ok=True)

        pdf_path = f"temp_pdfs/contract_{contract.contract_number}_{contract.student_id}_{contract.birth_year}.pdf"

        # Prepare PDF data
        pdf_data = {
            "shartnoma_raqami": contract.contract_number,
            "sana": {
                "kun": f"{contract.start_date.day:02d}",
                "oy": contract.start_date.strftime('%B'),
                "yil": str(contract.start_date.year)
            },
            "buyurtmachi": {
                "fio": custom_fields.customer.full_name,
                "pasport_seriya": custom_fields.customer.passport_number,
                "pasport_kim_bergan": custom_fields.customer.passport_issued_by,
                "pasport_qachon_bergan": str(custom_fields.customer.passport_issue_date),
                "manzil": custom_fields.customer.address,
                "telefon": custom_fields.customer.phone
            },
            "tarbiyalanuvchi": {
                "fio": f"{custom_fields.student.first_name} {custom_fields.student.last_name}",
                "tugilganlik_guvohnoma": custom_fields.student_birth_certificate.series,
                "guvohnoma_kim_bergan": custom_fields.student_birth_certificate.issued_by,
                "guvohnoma_qachon_bergan": str(custom_fields.student_birth_certificate.issue_date)
            },
            "shartnoma_muddati": {
                "boshlanish": contract.start_date.strftime('«%d» %B'),
                "tugash": contract.end_date.strftime('«%d» %B'),
                "yil": str(contract.start_date.year)
            },
            "tolov": {
                "oylik_narx": f"{contract.monthly_fee:,}".replace(",", " "),
                "oylik_narx_sozlar": "sum"  # You can add number-to-words conversion here
            }
        }

        pdf_data_cleaned = convert_dates(pdf_data)

        # Generate PDF
        generator = ContractGenerator(pdf_data_cleaned)
        pdf_generated_path = generator.generate(pdf_path)

        return FileResponse(
            path=pdf_generated_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_generated_path)
        )

    except Exception as e:
        # Rollback contract creation if PDF generation fails
        await db.delete(contract)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")


@router.get("/available-numbers/{group_id}/{birth_year}", response_model=DataResponse[ContractNumberInfo], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_available_numbers(
    group_id: int,
    birth_year: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get all available contract numbers for a group and birth year.

    Returns:
    - List of available sequence numbers (e.g., [1, 5, 12, 23])
    - Total capacity, used slots, and available slots
    - Whether the group is full for this birth year
    """
    # Get group
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group = group_result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail=f"Group with ID {group_id} not found")

    # Get available numbers
    try:
        available_numbers = await get_available_contract_numbers(db, group_id, birth_year)
    except ContractNumberAllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    total_used = group.capacity - len(available_numbers)
    is_full = len(available_numbers) == 0

    return DataResponse(data=ContractNumberInfo(
        group_id=group_id,
        group_name=group.name,
        group_capacity=group.capacity,
        birth_year=birth_year,
        available_numbers=available_numbers,
        total_available=len(available_numbers),
        total_used=total_used,
        is_full=is_full
    ))


@router.get("/next-available/{group_id}/{birth_year}", response_model=DataResponse[NextAvailableNumber], dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_next_available_number(
    group_id: int,
    birth_year: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get the next available contract number for a group and birth year.

    Useful for suggesting a contract number during contract creation.

    Returns:
    - The next available sequence number
    - The formatted contract number (e.g., "N12020")
    - Whether the group is full
    """
    # Get next available
    next_seq = await get_next_available_sequence(db, group_id, birth_year)

    if next_seq is None:
        return DataResponse(data=NextAvailableNumber(
            next_available=None,
            contract_number=None,
            birth_year=birth_year,
            is_full=True
        ))

    contract_number = f"N{next_seq}{birth_year}"

    return DataResponse(data=NextAvailableNumber(
        next_available=next_seq,
        contract_number=contract_number,
        birth_year=birth_year,
        is_full=False
    ))

import io
import httpx
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse

@router.get("/{year}/{contract_number}/pdf", dependencies=[Depends(require_permission(PERM_CONTRACTS_VIEW))])
async def get_contract_pdf_url(
    year: int,
    contract_number: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get contract PDF URL by year and contract number.
    Instead of returning the actual PDF stream, this endpoint returns the S3 URL.

    Example:
        GET /contracts/2025/N12017/pdf
        → Returns: {"pdf_url": "https://bucket.s3.region.amazonaws.com/contract-pdfs/N12017_xxx.pdf"}
    """

    # Find contract in DB
    result = await db.execute(
        select(Contract).where(
            and_(
                Contract.contract_number == contract_number,
                Contract.archive_year == year
            )
        )
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=404,
            detail=f"Contract {contract_number} for year {year} not found"
        )

    if not contract.final_pdf_url:
        raise HTTPException(
            status_code=404,
            detail=f"PDF not generated for contract {contract_number} yet"
        )

    # Return JSON with the S3 URL
    return JSONResponse(content={"pdf_url": contract.final_pdf_url})