from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, File, Form, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, cast
from sqlalchemy.dialects.postgresql import JSONB
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO
from datetime import datetime, date
from app.core.db import get_db
from app.core.permissions import PERM_STUDENTS_VIEW, PERM_STUDENTS_EDIT
from app.models.domain import Student
from app.models.finance import Transaction
from app.models.attendance import Attendance, GateLog
from app.models.enums import StudentStatus, ContractStatus
from app.schemas.student import StudentRead, StudentCreate, StudentUpdate, StudentDebtInfo, StudentFullInfo, ParentRead
from app.schemas.contract import ContractRead
from app.schemas.transaction import TransactionRead
from app.schemas.attendance import AttendanceRead, GateLogRead
from app.schemas.common import DataResponse, PaginationMeta
from app.schemas.student_with_contract import StudentWithContractCreate, StudentWithContractResponse
from app.deps import require_permission, CurrentUser
from app.models.auth import User
from app.core.s3 import upload_image_to_s3
from app.utils.contract_pdf import ContractPDFGenerator

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
    archive_year: int | None = Query(None, description="Filter by archive year (defaults to current year)"),
    include_archived: bool = Query(False, description="Include archived students (default: only non-ARCHIVED)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get all students with optional filters.

    Default behavior:
    - Shows current year's students only
    - Excludes ARCHIVED students unless include_archived=true
    """
    from datetime import datetime as dt
    if archive_year is None:
        archive_year = dt.now().year

    query = select(Student).where(Student.archive_year == archive_year)

    # Default: exclude ARCHIVED students
    if not include_archived:
        query = query.where(Student.status != StudentStatus.ARCHIVED)

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

    count_query = select(func.count(Student.id)).where(Student.archive_year == archive_year)
    if not include_archived:
        count_query = count_query.where(Student.status != StudentStatus.ARCHIVED)
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

from dateutil.relativedelta import relativedelta
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException


@router.post("/create-with-contract", response_class=FileResponse)
async def create_student_with_contract(
    user: Annotated[User, Depends(require_permission(PERM_STUDENTS_EDIT))],
    db: Annotated[AsyncSession, Depends(get_db)],

    # ========== JSON DATA ==========
    student_data: str = Form(..., description="Student data as JSON"),
    contract_data: str = Form(..., description="Contract data as JSON"),

    # ========== DOCUMENT FILES (FormData) ==========
    passport_copy: UploadFile = File(..., description="Passport copy file"),
    form_086: UploadFile = File(..., description="Medical form 086 file"),
    heart_checkup: UploadFile = File(..., description="Heart checkup document file"),
    birth_certificate: UploadFile = File(..., description="Birth certificate file"),
        contract_image_1: UploadFile | None = File(None, description="Contract page 1 (optional)"),
        contract_image_2: UploadFile | None = File(None, description="Contract page 2 (optional)"),

):
    """
    Create student with contract and all documents in ONE operation.

    **student_data JSON structure:**
    ```json
    {
        "first_name": "Alvaro",
        "last_name": "Marata",
        "date_of_birth": "2010-12-06",
        "contract_number":"",
        "phone": "998901234567",
        "address": "Toshkent shahar",
        "status": "active",
        "group_id": 1
    }
    ```

    **contract_data JSON structure:**
    ```json
    {
       "buyurtmachi": {
        "fio": " Каримович Ахмедов  Каримович",
        "pasport_seriya": "AA 1234567",
        "pasport_kim_bergan": "Чилонзор тумани ИИБ",
        "pasport_qachon_bergan": "01.01.2024",
        "manzil": "Тошкент ш, Чилонзор тумани, 1-даха, 12-уй, 34-хонадон",
        "telefon": "+998 90 123 45 67"
    },
    "tarbiyalanuvchi": {
        "fio": "Ахмедов Шоҳруҳ Дилшодович",
        "tugilganlik_guvohnoma": "I-AA 1234567",
        "guvohnoma_kim_bergan": "Чилонзор тумани ФХДЁ бўлими илонзор тумани",
        "guvohnoma_qachon_bergan": "01.01.2016"
    },
    "shartnoma_muddati": {
        "boshlanish": "2025-01-01",
        "tugash": "31",
         "yil": 2030
    },
    "tolov": {
        "oylik_narx": "600 000",
        "oylik_narx_sozlar": "олти юз минг"
    }
    }
    ```

    Complete workflow:
    1. Parse JSON data from student_data and contract_data
    2. Upload 9 files to AWS S3 automatically
    3. Create student and contract with ACTIVE status
    4. Generate PDF contract using contractdoc.py logic
    5. Return generated PDF file
    """
    from app.models.domain import Group, Contract, WaitingList
    from app.models.enums import ContractStatus, StudentStatus
    from app.services.contract_allocation import (
        get_available_contract_numbers,
        is_group_full,
        ContractNumberAllocationError
    )
    import json
    import os
    import tempfile
    from datetime import datetime

    # Parse JSON data
    try:
        student_info = json.loads(student_data)
        contract_info = json.loads(contract_data)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    # Extract required fields from student_data
    first_name = student_info.get("first_name")
    last_name = student_info.get("last_name")
    date_of_birth = student_info.get("date_of_birth")
    contract_number=student_info.get("contract_number")
    phone = student_info.get("phone")
    address = student_info.get("address")
    status = student_info.get("status", "active")
    group_id = student_info.get("group_id")

    # Validate required fields
    if not all([first_name, last_name, date_of_birth, group_id]):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields in student_data: first_name, last_name, date_of_birth, group_id"
        )
    contract_images_urls = []
    if contract_image_1:
        contract_images_urls.append(upload_image_to_s3(contract_image_1, "contracts"))
    if contract_image_2:
        contract_images_urls.append(upload_image_to_s3(contract_image_2, "contracts"))

    # Extract contract fields
    buyurtmachi = contract_info.get("buyurtmachi", {})
    tarbiyalanuvchi = contract_info.get("tarbiyalanuvchi", {})
    shartnoma_muddati = contract_info.get("shartnoma_muddati", {})
    tolov = contract_info.get("tolov", {})

    # Get birth year
    birth_year = tarbiyalanuvchi.get("tugilganlik_yil")
    if not birth_year:
        raise HTTPException(status_code=400, detail="tugilganlik_yil is required in contract_data.tarbiyalanuvchi")

    # Validate group exists
    group_result = await db.execute(select(Group).where(Group.id == group_id))
    group = group_result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail=f"Group with ID {group_id} not found")

    # Check if group is full for this birth year
    group_full = await is_group_full(db, group_id, birth_year)

    if group_full:
        raise HTTPException(
            status_code=409,
            detail=f"Group is full for birth year {birth_year}. Cannot create contract."
        )

    # Upload all files to S3
    # Upload all files to S3
    try:
        # Fayl pointerlarini qayta boshiga olish
        for f in [passport_copy, form_086, heart_checkup, birth_certificate, contract_image_1, contract_image_2]:
            if f is not None:
                f.file.seek(0)

        # Asosiy hujjatlar
        passport_copy_url = await upload_image_to_s3(passport_copy, "student-documents")
        form_086_url = await upload_image_to_s3(form_086, "student-documents")
        heart_checkup_url = await upload_image_to_s3(heart_checkup, "student-documents")
        birth_certificate_url = await upload_image_to_s3(birth_certificate, "student-documents")

        contract_images_urls = []
        if contract_image_1:
            contract_images_urls.append(await upload_image_to_s3(contract_image_1, "contracts"))
        if contract_image_2:
            contract_images_urls.append(await upload_image_to_s3(contract_image_2, "contracts"))


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading files to S3: {str(e)}")

    # Parse date_of_birth if string
    if isinstance(date_of_birth, str):
        from datetime import datetime
        date_of_birth = datetime.strptime(date_of_birth, "%Y-%m-%d").date()

    # Get current year for archive
    current_year = datetime.now().year

    # Create student
    student_status = StudentStatus.ACTIVE if status.lower() == "active" else StudentStatus.INACTIVE
    student = Student(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone=phone,
        address=address,
        status=student_status,
        group_id=group_id,
        archive_year=current_year  # Set current year as archive year
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    # Allocate contract number
    try:
        available_numbers = await get_available_contract_numbers(db, group_id, birth_year, current_year)
        if not available_numbers:
            raise ContractNumberAllocationError(
                f"No available contract numbers for group {group.name} and birth year {birth_year}"
            )
        sequence_number = available_numbers[0]
        contract_number = contract_info.get("contract_number")
        if not contract_number:
            raise HTTPException(status_code=400, detail="contract_number is required in contract_data")

    except ContractNumberAllocationError as e:
        # Rollback student creation if contract number allocation fails
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    # Parse contract dates
    start_date_str = shartnoma_muddati.get("boshlanish")
    end_date_str = shartnoma_muddati.get("tugash")
    year_val = shartnoma_muddati.get("yil")
    monthly_fee_raw = tolov.get("oylik_narx", 0)


    try:
        if isinstance(monthly_fee_raw, str):
            # Masalan: "600 000" yoki "600,000" yoki "600000"
            cleaned = monthly_fee_raw.replace(" ", "").replace(",", "")
            monthly_fee = Decimal(cleaned)
        else:
            monthly_fee = Decimal(monthly_fee_raw)
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"To‘lov miqdati noto‘g‘ri formatda yuborilgan: {monthly_fee_raw!r}"
        )

    # --- Sana formatlarini tekshirish (boshlanish) ---
    try:
        if start_date_str:
            # Foydalanuvchi "2025-01-01" formatda yuboradi
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            raise ValueError("boshlanish sanasi kiritilmagan")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sana formati noto‘g‘ri (boshlanish): {str(e)}")

    # --- Tugash sanasi ---
    try:
        if end_date_str and end_date_str.isdigit():
            # Masalan: "31" → 31 dekabr {yil}
            end_date = datetime(int(year_val or start_date.year), 12, int(end_date_str)).date()
        elif end_date_str:
            # Agar foydalanuvchi ISO formatda yuborsa
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            # Tugash kiritilmagan bo‘lsa — 1 yilga uzaytiramiz
            end_date = start_date + relativedelta(years=1)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sana formati noto‘g‘ri (tugash): {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sana formati noto‘g‘ri (tugash): {str(e)}")

    # Convert data to JSON strings for storage
    contract_images_json_str = json.dumps(contract_images_urls)
    custom_fields_json_str = json.dumps(contract_info, ensure_ascii=False, default=str)
    existing_contract = await db.execute(
        select(Contract).where(Contract.contract_number == contract_number)
    )
    if existing_contract.scalar():
        raise HTTPException(
            status_code=400,
            detail=f"Shartnoma raqami '{contract_number}' allaqachon mavjud."
        )
    # Create contract in ACTIVE status (no signature needed)
    contract = Contract(
        contract_number=contract_number,
        birth_year=birth_year,
        sequence_number=sequence_number,
        start_date=start_date,
        end_date=end_date,
        monthly_fee=monthly_fee,
        status=ContractStatus.ACTIVE,
        student_id=student.id,
        group_id=group_id,
        archive_year=current_year,  # Set current year as archive year
        passport_copy_url=passport_copy_url,
        form_086_url=form_086_url,
        heart_checkup_url=heart_checkup_url,
        birth_certificate_url=birth_certificate_url,
        contract_images_urls=contract_images_json_str,
        custom_fields=custom_fields_json_str,
        signature_token=None  # No signature needed
    )

    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    # Prepare data for PDF generation (contractdoc.py format)
    # Parse sana from start_date
    sana_obj = start_date
    months_uz = {
        1: "январь", 2: "февраль", 3: "март", 4: "апрель",
        5: "май", 6: "июнь", 7: "июль", 8: "август",
        9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
    }

    pdf_data = {
        "shartnoma_raqami": contract_number,
        "sana": {
            "kun": f"{sana_obj.day:02d}",
            "oy": months_uz.get(sana_obj.month, ""),
            "yil": str(sana_obj.year)
        },
        "buyurtmachi": buyurtmachi,
        "tarbiyalanuvchi": tarbiyalanuvchi,
        "shartnoma_muddati": {
            "boshlanish": start_date.strftime('«%d» %B'),
            "tugash": end_date.strftime('«%d» %B'),
            "yil": str(start_date.year)
        },
        "tolov": {
            "oylik_narx": f"{monthly_fee:,.0f}".replace(",", " "),
            "oylik_narx_sozlar": "sum"  # You can add number-to-words conversion here
        }
    }

    # Generate PDF in temp file
    import time

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = temp_pdf.name
    temp_pdf.close()  # ❗ Fayl descriptorni yopamiz

    try:
        generator = ContractPDFGenerator(pdf_data)

        output_path = pdf_path  # original temp fayl nomi
        generated_pdf_path = generator.generate(output_path)

        # ✅ Himoya: generate() hech narsa qaytarmasa yoki dict qaytarsa
        if not generated_pdf_path or not isinstance(generated_pdf_path, (str, os.PathLike)):
            raise ValueError(f"ContractPDFGenerator.generate() noto‘g‘ri qiymat qaytardi: {type(generated_pdf_path)}")

        # Return PDF response (FastAPI uni o‘zi o‘qiydi)
        return FileResponse(
            path=generated_pdf_path,
            filename=f"contract_{contract_number}.pdf",
            media_type="application/pdf"
        )

    except Exception as e:
        # Faylni xavfsiz o‘chirish
        try:
            time.sleep(0.2)  # Windows lock'ni ozgina kutish
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
        except PermissionError:
            print(f"⚠️ Fayl o‘chirilmadi (lock): {pdf_path}")

        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


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
