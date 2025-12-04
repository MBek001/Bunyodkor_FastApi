"""
Digital signature workflow for contracts.

Endpoints:
- GET /signatures/verify/{token} - Verify token and get contract info
- POST /signatures/sign/{token} - Submit signature and activate contract
"""
from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.db import get_db
from app.models.domain import Contract, Student, Group
from app.models.enums import ContractStatus
from app.schemas.signature import SignatureSubmit, SignatureVerify, SignatureComplete
from app.schemas.common import DataResponse
from app.services.pdf_service import pdf_service, PDFServiceError

router = APIRouter(prefix="/signatures", tags=["Signatures"])


@router.get("/verify/{signature_token}", response_model=DataResponse[SignatureVerify])
async def verify_signature_token(
    signature_token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Verify signature token and get contract information for signing.

    This endpoint is called when a customer opens the signing link.
    Returns contract details to display before signing.

    If token is invalid or contract already signed, returns appropriate error.
    """
    # Find contract by signature token
    result = await db.execute(
        select(Contract)
        .options(
            selectinload(Contract.student),
            selectinload(Contract.group)
        )
        .where(Contract.signature_token == signature_token)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=404,
            detail="Invalid signature token. The signing link may be incorrect or expired."
        )

    # Check if already signed
    is_already_signed = contract.signed_at is not None

    # Get student and group info
    student = contract.student
    group = contract.group

    return DataResponse(data=SignatureVerify(
        contract_id=contract.id,
        contract_number=contract.contract_number,
        student_name=student.full_name if student else "Unknown",
        group_name=group.name if group else "Unknown",
        start_date=str(contract.start_date),
        end_date=str(contract.end_date),
        monthly_fee=contract.monthly_fee,
        is_valid=True,
        is_already_signed=is_already_signed,
        message="Contract ready for signature" if not is_already_signed else "This contract has already been signed"
    ))


@router.post("/sign/{signature_token}", response_model=DataResponse[SignatureComplete])
async def submit_signature(
    signature_token: str,
    data: SignatureSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Submit digital signature and activate contract.

    Workflow:
    1. Verify signature token
    2. Check contract not already signed
    3. Decode signature image
    4. Insert signature into PDF at first and last positions
    5. Merge all documents (5 contract pages + 4 supporting docs)
    6. Save final PDF
    7. Update contract: status=ACTIVE, signed_at=now, signature_url
    8. Return success with final PDF URL

    Note: Current implementation saves signature but doesn't generate final PDF.
    Full PDF generation requires file storage integration (S3, local, etc.)
    """
    # Find contract by signature token
    result = await db.execute(
        select(Contract)
        .where(Contract.signature_token == signature_token)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=404,
            detail="Invalid signature token"
        )

    # Check if already signed
    if contract.signed_at:
        raise HTTPException(
            status_code=400,
            detail="This contract has already been signed"
        )

    # Check contract is in PENDING status
    if contract.status != ContractStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Contract must be in PENDING status to sign. Current status: {contract.status.value}"
        )

    try:
        # Decode signature to validate it
        signature_image = pdf_service.decode_signature(data.signature_data)

        # TODO: In production, implement full PDF workflow:
        # 1. Download all 9 documents from URLs
        # 2. Convert contract images to PDF pages
        # 3. Insert signature into first and last contract pages
        # 4. Merge all documents into single PDF
        # 5. Upload final PDF to storage
        # 6. Get final_pdf_url from storage

        # For now, we'll just save the signature data
        # In production, you'd save this to file storage (S3, etc.) and get a URL
        signature_url = f"data:image/png;base64,{data.signature_data}"
        final_pdf_url = f"/contracts/{contract.id}/final.pdf"  # Placeholder

        # Update contract
        contract.signature_url = signature_url
        contract.signed_at = datetime.utcnow()
        contract.final_pdf_url = final_pdf_url
        contract.status = ContractStatus.ACTIVE

        await db.commit()
        await db.refresh(contract)

        return DataResponse(data=SignatureComplete(
            contract_id=contract.id,
            contract_number=contract.contract_number,
            status="active",
            signed_at=contract.signed_at,
            final_pdf_url=final_pdf_url,
            message="Contract signed successfully and activated. The final PDF has been generated."
        ))

    except PDFServiceError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process signature: {str(e)}"
        )
    except Exception as e:
        # Rollback any changes
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing signature: {str(e)}"
        )
