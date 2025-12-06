from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, cast
from sqlalchemy.dialects.postgresql import JSONB
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
from datetime import datetime
from app.core.db import get_db
from app.core.permissions import PERM_STUDENTS_VIEW, PERM_STUDENTS_EDIT
from app.models.domain import Student
from app.models.finance import Transaction
from app.models.attendance import Attendance, GateLog
from app.schemas.student import StudentRead, StudentCreate, StudentUpdate, StudentDebtInfo, StudentFullInfo, ParentRead
from app.schemas.contract import ContractRead
from app.schemas.transaction import TransactionRead
from app.schemas.attendance import AttendanceRead, GateLogRead
from app.schemas.common import DataResponse, PaginationMeta
from app.schemas.student_with_contract import StudentWithContractCreate, StudentWithContractResponse
from app.deps import require_permission, CurrentUser

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("/search", response_model=DataResponse[list[StudentRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def search_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str = Query(..., description="Search by first name, last name, contract number, phone, or parent email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Comprehensive search for students by:
    - First name
    - Last name
    - Contract number
    - Phone number
    - Parent email
    """
    from app.models.domain import Contract, Parent

    # Search students by name or phone
    students_query = select(Student).where(
        or_(
            Student.first_name.ilike(f"%{query}%"),
            Student.last_name.ilike(f"%{query}%"),
            Student.phone.ilike(f"%{query}%"),
        )
    ).distinct()

    # Search by contract number
    contracts_result = await db.execute(
        select(Contract.student_id).where(Contract.contract_number.ilike(f"%{query}%"))
    )
    student_ids_from_contracts = [row[0] for row in contracts_result.fetchall()]

    # Search by parent email
    parents_result = await db.execute(
        select(Parent.student_id).where(Parent.email.ilike(f"%{query}%"))
    )
    student_ids_from_parents = [row[0] for row in parents_result.fetchall()]

    # Combine all student IDs
    all_student_ids = set(student_ids_from_contracts + student_ids_from_parents)

    # If we found students via contracts or parents, add them to the query
    if all_student_ids:
        students_query = select(Student).where(
            or_(
                Student.first_name.ilike(f"%{query}%"),
                Student.last_name.ilike(f"%{query}%"),
                Student.phone.ilike(f"%{query}%"),
                Student.id.in_(all_student_ids)
            )
        ).distinct()

    # Apply pagination
    offset = (page - 1) * page_size
    result = await db.execute(students_query.offset(offset).limit(page_size))
    students = result.scalars().all()

    # Count total results
    count_query = select(func.count(Student.id.distinct())).where(
        or_(
            Student.first_name.ilike(f"%{query}%"),
            Student.last_name.ilike(f"%{query}%"),
            Student.phone.ilike(f"%{query}%"),
            Student.id.in_(all_student_ids) if all_student_ids else False
        )
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return DataResponse(
        data=[StudentRead.model_validate(s) for s in students],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
    )


@router.get("", response_model=DataResponse[list[StudentRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(Student)

    if search:
        query = query.where(
            or_(
                Student.first_name.ilike(f"%{search}%"),
                Student.last_name.ilike(f"%{search}%"),
            )
        )
    if group_id:
        query = query.where(Student.group_id == group_id)
    if status:
        query = query.where(Student.status == status)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    students = result.scalars().all()

    count_query = select(func.count(Student.id))
    if search:
        count_query = count_query.where(
            or_(
                Student.first_name.ilike(f"%{search}%"),
                Student.last_name.ilike(f"%{search}%"),
            )
        )
    if group_id:
        count_query = count_query.where(Student.group_id == group_id)
    if status:
        count_query = count_query.where(Student.status == status)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return DataResponse(
        data=[StudentRead.model_validate(s) for s in students],
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/unpaid", response_model=DataResponse[list[StudentDebtInfo]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_unpaid_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Optional[int] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    months: Optional[str] = Query(None, description="Comma-separated months (e.g., '1,2,3' for Jan, Feb, Mar)"),
    group_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get students who haven't paid for specified periods.

    Filters:
    - year: Target year (defaults to current year)
    - month: Single month to check (1-12)
    - months: Multiple months as comma-separated string (e.g., "1,2,3")
    - group_id: Filter by specific group

    Examples:
    - /unpaid?year=2025&month=1 - Debtors for January 2025
    - /unpaid?year=2025&months=1,2,3 - Debtors for Jan, Feb, Mar 2025
    - /unpaid?year=2025 - Debtors for any month in 2025
    - /unpaid?year=2025&group_id=5 - Debtors in group 5 for 2025
    """
    from app.models.domain import Contract
    from app.models.enums import ContractStatus, PaymentStatus
    from datetime import date

    # Default to current year
    today = date.today()
    target_year = year if year is not None else today.year

    # Parse target months
    target_months = []
    if months:
        # Parse comma-separated months
        try:
            target_months = [int(m.strip()) for m in months.split(',') if m.strip()]
            # Validate months
            for m in target_months:
                if m < 1 or m > 12:
                    raise HTTPException(status_code=400, detail=f"Invalid month: {m}. Must be between 1 and 12")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid months format. Use comma-separated numbers (e.g., '1,2,3')")
    elif month is not None:
        # Single month specified
        target_months = [month]
    else:
        # No months specified - check all 12 months of the year
        target_months = list(range(1, 13))

    # Build student query with filters
    students_query = select(Student).where(Student.status == "active")

    if group_id:
        students_query = students_query.where(Student.group_id == group_id)

    students_result = await db.execute(students_query)
    students = students_result.scalars().all()

    debt_info_list = []
    for student in students:
        # Get all contracts for this student (including terminated ones)
        contracts_result = await db.execute(
            select(Contract).where(Contract.student_id == student.id)
        )
        contracts = contracts_result.scalars().all()

        if not contracts:
            continue

        # Calculate debt across all target months
        total_expected = 0
        total_paid = 0
        active_contracts_count = 0

        for target_month in target_months:
            # Calculate expected payment for this month
            month_expected = 0
            target_date = date(target_year, target_month, 1)

            for contract in contracts:
                # Determine the effective end date (earliest of end_date or terminated_at)
                effective_end_date = contract.end_date
                if contract.terminated_at:
                    termination_date = contract.terminated_at.date()
                    if termination_date < effective_end_date:
                        effective_end_date = termination_date

                # Check if contract was active during this target month
                # Contract start month
                contract_start_month = contract.start_date.replace(day=1)
                contract_end_month = effective_end_date.replace(day=1)

                # Check if target month falls within contract period
                if contract_start_month <= target_date <= contract_end_month:
                    month_expected += float(contract.monthly_fee)
                    # Count as active if it was active in any of the target months
                    if contract.status == ContractStatus.ACTIVE or (
                        contract.status == ContractStatus.TERMINATED and
                        contract.terminated_at and
                        contract.terminated_at.date() >= target_date
                    ):
                        active_contracts_count = max(active_contracts_count, 1)

            # Add to total expected
            total_expected += month_expected

            # Check if student has paid for this specific month
            # Use PostgreSQL @> operator to check if JSON array contains the target month
            transactions_result = await db.execute(
                select(func.sum(Transaction.amount)).where(
                    Transaction.student_id == student.id,
                    Transaction.status == PaymentStatus.SUCCESS,
                    Transaction.payment_year == target_year,
                    Transaction.payment_months.op('@>')(cast([target_month], JSONB))
                )
            )
            month_paid = transactions_result.scalar() or 0
            total_paid += float(month_paid)

        # If no expected payment for any month, skip
        if total_expected == 0:
            continue

        # Calculate total debt
        debt_amount = total_expected - total_paid

        if debt_amount > 0.01:  # Only include if debt > 1 cent (avoid floating point errors)
            debt_info_list.append(StudentDebtInfo(
                student=StudentRead.model_validate(student),
                total_expected=total_expected,
                total_paid=total_paid,
                debt_amount=debt_amount,
                active_contracts_count=len([c for c in contracts if c.status == ContractStatus.ACTIVE])
            ))

    # Sort by debt amount (highest first)
    debt_info_list.sort(key=lambda x: x.debt_amount, reverse=True)

    # Apply pagination
    offset = (page - 1) * page_size
    paginated_list = debt_info_list[offset:offset + page_size]
    total = len(debt_info_list)

    return DataResponse(
        data=paginated_list,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/unpaid/export", dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def export_unpaid_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    year: Optional[int] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    months: Optional[str] = Query(None, description="Comma-separated months (e.g., '1,2,3')"),
    group_id: Optional[int] = None,
):
    """
    Export unpaid students data to Excel file.

    Same filters as /unpaid endpoint:
    - year: Target year (defaults to current year)
    - month: Single month to check (1-12)
    - months: Multiple months as comma-separated string
    - group_id: Filter by specific group
    """
    from app.models.domain import Contract, Group
    from app.models.enums import ContractStatus, PaymentStatus
    from datetime import date

    # Default to current year
    today = date.today()
    target_year = year if year is not None else today.year

    # Parse target months
    target_months = []
    if months:
        try:
            target_months = [int(m.strip()) for m in months.split(',') if m.strip()]
            for m in target_months:
                if m < 1 or m > 12:
                    raise HTTPException(status_code=400, detail=f"Invalid month: {m}. Must be between 1 and 12")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid months format. Use comma-separated numbers")
    elif month is not None:
        target_months = [month]
    else:
        target_months = list(range(1, 13))

    # Build student query with filters
    students_query = select(Student).where(Student.status == "active")

    if group_id:
        students_query = students_query.where(Student.group_id == group_id)

    students_result = await db.execute(students_query)
    students = students_result.scalars().all()

    # Get group name for filename if filtering by group
    group_name = ""
    if group_id:
        group_result = await db.execute(select(Group).where(Group.id == group_id))
        group = group_result.scalar_one_or_none()
        if group:
            group_name = f"_{group.name.replace(' ', '_')}"

    debt_info_list = []
    for student in students:
        contracts_result = await db.execute(
            select(Contract).where(Contract.student_id == student.id)
        )
        contracts = contracts_result.scalars().all()

        if not contracts:
            continue

        total_expected = 0
        total_paid = 0

        for target_month in target_months:
            month_expected = 0
            target_date = date(target_year, target_month, 1)

            for contract in contracts:
                effective_end_date = contract.end_date
                if contract.terminated_at:
                    termination_date = contract.terminated_at.date()
                    if termination_date < effective_end_date:
                        effective_end_date = termination_date

                contract_start_month = contract.start_date.replace(day=1)
                contract_end_month = effective_end_date.replace(day=1)

                if contract_start_month <= target_date <= contract_end_month:
                    month_expected += float(contract.monthly_fee)

            total_expected += month_expected

            transactions_result = await db.execute(
                select(func.sum(Transaction.amount)).where(
                    Transaction.student_id == student.id,
                    Transaction.status == PaymentStatus.SUCCESS,
                    Transaction.payment_year == target_year,
                    Transaction.payment_months.op('@>')(cast([target_month], JSONB))
                )
            )
            month_paid = transactions_result.scalar() or 0
            total_paid += float(month_paid)

        if total_expected == 0:
            continue

        debt_amount = total_expected - total_paid

        if debt_amount > 0.01:
            # Get group name for this student
            student_group_name = ""
            if student.group_id:
                student_group_result = await db.execute(select(Group).where(Group.id == student.group_id))
                student_group = student_group_result.scalar_one_or_none()
                if student_group:
                    student_group_name = student_group.name

            debt_info_list.append({
                "student_id": student.id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "phone": student.phone or "",
                "group": student_group_name,
                "total_expected": total_expected,
                "total_paid": total_paid,
                "debt_amount": debt_amount,
                "active_contracts": len([c for c in contracts if c.status == ContractStatus.ACTIVE])
            })

    # Sort by debt amount (highest first)
    debt_info_list.sort(key=lambda x: x["debt_amount"], reverse=True)

    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Unpaid Students"

    # Define header style
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    header_alignment = Alignment(horizontal="center", vertical="center")

    # Define headers
    headers = [
        "ID",
        "First Name",
        "Last Name",
        "Phone",
        "Group",
        "Expected Amount",
        "Paid Amount",
        "Debt Amount",
        "Active Contracts"
    ]

    # Write headers
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    # Write data
    for row_num, debt_info in enumerate(debt_info_list, 2):
        ws.cell(row=row_num, column=1, value=debt_info["student_id"])
        ws.cell(row=row_num, column=2, value=debt_info["first_name"])
        ws.cell(row=row_num, column=3, value=debt_info["last_name"])
        ws.cell(row=row_num, column=4, value=debt_info["phone"])
        ws.cell(row=row_num, column=5, value=debt_info["group"])
        ws.cell(row=row_num, column=6, value=debt_info["total_expected"])
        ws.cell(row=row_num, column=7, value=debt_info["total_paid"])
        ws.cell(row=row_num, column=8, value=debt_info["debt_amount"])
        ws.cell(row=row_num, column=9, value=debt_info["active_contracts"])

    # Adjust column widths
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 20
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 15
    ws.column_dimensions['I'].width = 18

    # Add summary row
    if debt_info_list:
        summary_row = len(debt_info_list) + 3
        ws.cell(row=summary_row, column=1, value="TOTAL").font = Font(bold=True)
        ws.cell(row=summary_row, column=6, value=sum(d["total_expected"] for d in debt_info_list)).font = Font(bold=True)
        ws.cell(row=summary_row, column=7, value=sum(d["total_paid"] for d in debt_info_list)).font = Font(bold=True)
        ws.cell(row=summary_row, column=8, value=sum(d["debt_amount"] for d in debt_info_list)).font = Font(bold=True)

    # Save to BytesIO
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    # Generate filename
    months_str = ",".join(map(str, target_months)) if len(target_months) <= 3 else "all"
    filename = f"unpaid_students_{target_year}_{months_str}{group_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    # Return as streaming response
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("", response_model=DataResponse[StudentRead], dependencies=[Depends(require_permission(PERM_STUDENTS_EDIT))])
async def create_student(
    data: StudentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if data.face_id:
        existing_face_id = await db.execute(select(Student).where(Student.face_id == data.face_id))
        if existing_face_id.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Face ID already exists. Please use a unique Face ID")

    if data.group_id:
        from app.models.domain import Group
        group_result = await db.execute(select(Group).where(Group.id == data.group_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Group with ID {data.group_id} not found")

    student = Student(**data.model_dump())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return DataResponse(data=StudentRead.model_validate(student))


@router.post("/create-with-contract", response_model=DataResponse[StudentWithContractResponse], dependencies=[Depends(require_permission(PERM_STUDENTS_EDIT))])
async def create_student_with_contract(
    data: StudentWithContractCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create student with contract and all documents in ONE operation.

    Complete workflow:
    1. Upload all 9 documents first using /uploads/student-documents and /uploads/contract-documents
    2. Submit this request with all student data, group selection, document URLs, and handwritten fields
    3. System validates group capacity for birth year
    4. If full → adds to waiting list and returns error
    5. If space → creates student, allocates contract number, creates contract
    6. Returns student ID, contract ID, and signature link

    This endpoint combines:
    - Student creation
    - Group selection
    - Document upload validation
    - Contract number allocation
    - Contract creation with PENDING status
    - Signature link generation

    All in one atomic operation!
    """
    from app.models.domain import Group, Contract, WaitingList
    from app.models.enums import ContractStatus
    from app.services.contract_allocation import (
        get_available_contract_numbers,
        is_group_full,
        ContractNumberAllocationError
    )
    import json
    import uuid

    # Validate group exists
    group_result = await db.execute(select(Group).where(Group.id == data.group_id))
    group = group_result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail=f"Group with ID {data.group_id} not found")

    # Get birth year from handwritten data
    birth_year = data.custom_fields.student.birth_year

    # Check if group is full for this birth year
    group_full = await is_group_full(db, data.group_id, birth_year)

    if group_full:
        # Create student first (so we have student_id for waiting list)
        student = Student(
            full_name=data.full_name,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            phone=data.phone,
            email=data.email,
            address=data.address,
            status=data.status,
            parent_name=data.parent_name,
            parent_phone=data.parent_phone,
            group_id=None  # Don't assign group yet since it's full
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)

        # Add to waiting list
        waiting_entry = WaitingList(
            student_id=student.id,
            group_id=data.group_id,
            priority=0,
            notes=f"Group full for birth year {birth_year}. All documents uploaded and ready for contract.",
            added_by_user_id=user.id
        )
        db.add(waiting_entry)
        await db.commit()

        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Group is full for birth year {birth_year}. Student created and added to waiting list.",
                "student_id": student.id,
                "waiting_list_id": waiting_entry.id,
                "waiting_list": True,
                "birth_year": birth_year
            }
        )

    # Check if face_id already exists (if provided)
    if hasattr(data, 'face_id') and data.face_id:
        existing_face_id = await db.execute(select(Student).where(Student.face_id == data.face_id))
        if existing_face_id.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Face ID already exists. Please use a unique Face ID")

    # Create student
    student = Student(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        phone=data.phone,
        email=data.email,
        address=data.address,
        status=data.status,
        parent_name=data.parent_name,
        parent_phone=data.parent_phone,
        group_id=data.group_id
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    # Allocate contract number using birth year from custom_fields
    try:
        available_numbers = await get_available_contract_numbers(db, data.group_id, birth_year)
        if not available_numbers:
            raise ContractNumberAllocationError(
                f"No available contract numbers for group {group.name} and birth year {birth_year}"
            )

        sequence_number = available_numbers[0]
        contract_number = f"N{sequence_number}{birth_year}"
    except ContractNumberAllocationError as e:
        # Rollback student creation if contract number allocation fails
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    # Generate unique signature token
    signature_token = str(uuid.uuid4())

    # Convert data to JSON strings for storage
    contract_images_json = json.dumps(data.contract_images_urls)
    custom_fields_json = json.dumps(data.custom_fields.model_dump(), ensure_ascii=False, default=str)

    # Get dates and fee from custom_fields.contract_terms
    start_date = data.custom_fields.contract_terms.contract_start_date
    end_date = data.custom_fields.contract_terms.contract_end_date
    monthly_fee = data.custom_fields.contract_terms.monthly_fee

    # Create contract in PENDING status (waiting for signature)
    contract = Contract(
        contract_number=contract_number,
        birth_year=birth_year,
        sequence_number=sequence_number,
        start_date=start_date,
        end_date=end_date,
        monthly_fee=monthly_fee,
        status=ContractStatus.PENDING,
        student_id=student.id,
        group_id=data.group_id,
        passport_copy_url=data.passport_copy_url,
        form_086_url=data.form_086_url,
        heart_checkup_url=data.heart_checkup_url,
        birth_certificate_url=data.birth_certificate_url,
        contract_images_urls=contract_images_json,
        custom_fields=custom_fields_json,
        signature_token=signature_token
    )

    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    # Generate signing link
    signature_link = f"/signatures/sign/{signature_token}"

    return DataResponse(data=StudentWithContractResponse(
        student_id=student.id,
        student_full_name=student.full_name,
        contract_id=contract.id,
        contract_number=contract_number,
        birth_year=birth_year,
        sequence_number=sequence_number,
        group_id=group.id,
        group_name=group.name,
        signature_token=signature_token,
        signature_link=signature_link,
        contract_status="pending_signature",
        message=f"Student '{student.full_name}' created successfully with contract {contract_number}. Send the signing link to the customer."
    ))


@router.get("/{student_id}", response_model=DataResponse[StudentRead], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return DataResponse(data=StudentRead.model_validate(student))


@router.get("/fullinfo/{student_id}", response_model=DataResponse[StudentFullInfo], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_full_info(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get complete student information including:
    - Student details
    - Parents
    - Contracts
    - Group
    - Coach (teacher)
    - Payment history (transactions)
    - Attendance records
    """
    from app.models.domain import Contract, Parent, Group
    from app.models.auth import User
    from sqlalchemy.orm import selectinload

    # Fetch student
    student_result = await db.execute(select(Student).where(Student.id == student_id))
    student = student_result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Fetch parents
    parents_result = await db.execute(select(Parent).where(Parent.student_id == student_id))
    parents = parents_result.scalars().all()

    # Fetch contracts
    contracts_result = await db.execute(select(Contract).where(Contract.student_id == student_id))
    contracts = contracts_result.scalars().all()

    # Fetch group and coach if student has a group
    group = None
    coach = None
    if student.group_id:
        group_result = await db.execute(select(Group).where(Group.id == student.group_id))
        group = group_result.scalar_one_or_none()

        if group and group.coach_id:
            coach_result = await db.execute(
                select(User).where(User.id == group.coach_id)
            )
            coach = coach_result.scalar_one_or_none()

    # Fetch transactions
    transactions_result = await db.execute(
        select(Transaction).where(Transaction.student_id == student_id).order_by(Transaction.created_at.desc())
    )
    transactions = transactions_result.scalars().all()

    # Fetch attendance records
    attendances_result = await db.execute(
        select(Attendance).where(Attendance.student_id == student_id).order_by(Attendance.created_at.desc())
    )
    attendances = attendances_result.scalars().all()

    # Build the full info response
    from app.schemas.group import GroupRead
    from app.schemas.auth import UserRead

    full_info = StudentFullInfo(
        student=StudentRead.model_validate(student),
        parents=[ParentRead.model_validate(p) for p in parents],
        contracts=[ContractRead.model_validate(c) for c in contracts],
        group=GroupRead.model_validate(group) if group else None,
        coach=UserRead.model_validate(coach) if coach else None,
        transactions=[TransactionRead.model_validate(t) for t in transactions],
        attendances=[AttendanceRead.model_validate(a) for a in attendances],
    )

    return DataResponse(data=full_info)


@router.patch("/{student_id}", response_model=DataResponse[StudentRead], dependencies=[Depends(require_permission(PERM_STUDENTS_EDIT))])
async def update_student(
    student_id: int,
    data: StudentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_data = data.model_dump(exclude_unset=True)

    if "face_id" in update_data and update_data["face_id"] is not None:
        existing_face_id = await db.execute(
            select(Student).where(Student.face_id == update_data["face_id"], Student.id != student_id)
        )
        if existing_face_id.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Face ID already exists. Please use a unique Face ID")

    if "group_id" in update_data and update_data["group_id"] is not None:
        from app.models.domain import Group
        group_result = await db.execute(select(Group).where(Group.id == update_data["group_id"]))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Group with ID {update_data['group_id']} not found")

    for field, value in update_data.items():
        setattr(student, field, value)

    await db.commit()
    await db.refresh(student)
    return DataResponse(data=StudentRead.model_validate(student))


@router.get("/{student_id}/contracts", response_model=DataResponse[list[ContractRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_contracts(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.domain import Contract
    result = await db.execute(select(Contract).where(Contract.student_id == student_id))
    contracts = result.scalars().all()
    return DataResponse(data=[ContractRead.model_validate(c) for c in contracts])


@router.get("/{student_id}/transactions", response_model=DataResponse[list[TransactionRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_transactions(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Transaction).where(Transaction.student_id == student_id))
    transactions = result.scalars().all()
    return DataResponse(data=[TransactionRead.model_validate(t) for t in transactions])


@router.get("/{student_id}/attendance", response_model=DataResponse[list[AttendanceRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_attendance(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Attendance).where(Attendance.student_id == student_id))
    attendance = result.scalars().all()
    return DataResponse(data=[AttendanceRead.model_validate(a) for a in attendance])


@router.get("/{student_id}/gatelogs", response_model=DataResponse[list[GateLogRead]], dependencies=[Depends(require_permission(PERM_STUDENTS_VIEW))])
async def get_student_gatelogs(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(GateLog).where(GateLog.student_id == student_id))
    logs = result.scalars().all()
    return DataResponse(data=[GateLogRead.model_validate(l) for l in logs])


@router.delete("/{student_id}", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_STUDENTS_EDIT))])
async def delete_student(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    await db.delete(student)
    await db.commit()

    return DataResponse(data={"message": "Student deleted successfully"})


@router.post("/bulk-delete", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_STUDENTS_EDIT))])
async def bulk_delete_students(
    student_ids: list[int],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Bulk delete multiple students by their IDs"""
    if not student_ids:
        raise HTTPException(status_code=400, detail="No student IDs provided")

    deleted_count = 0
    errors = []

    for student_id in student_ids:
        try:
            result = await db.execute(select(Student).where(Student.id == student_id))
            student = result.scalar_one_or_none()

            if not student:
                errors.append({"student_id": student_id, "error": "Student not found"})
                continue

            await db.delete(student)
            deleted_count += 1
        except Exception as e:
            errors.append({"student_id": student_id, "error": str(e)})

    await db.commit()

    return DataResponse(data={
        "message": f"Deleted {deleted_count} student(s)",
        "deleted_count": deleted_count,
        "total_requested": len(student_ids),
        "errors": errors if errors else None
    })
