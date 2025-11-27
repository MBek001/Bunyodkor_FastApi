# BUNYODKOR CIMS - Backend Developer Documentation

## Project Architecture

### Tech Stack
- **Framework**: FastAPI 0.109
- **ORM**: SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL with asyncpg driver
- **Migrations**: Alembic
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt (via passlib)
- **Python**: 3.11+

### Project Structure

```
Bunyodkor_FastApi/
├── app/
│   ├── core/
│   │   ├── config.py          # Pydantic Settings
│   │   ├── db.py              # Async DB engine & session
│   │   ├── security.py        # JWT & password utilities
│   │   └── permissions.py     # RBAC permission constants
│   ├── models/
│   │   ├── auth.py            # User, Role, Permission
│   │   ├── domain.py          # Student, Parent, Group, Contract
│   │   ├── finance.py         # Transaction
│   │   ├── attendance.py      # Session, Attendance, GateLog
│   │   ├── settings.py        # SystemSettings
│   │   ├── enums.py           # All Enum classes
│   │   └── base.py            # TimestampMixin
│   ├── schemas/
│   │   ├── common.py          # DataResponse, PaginationMeta
│   │   ├── auth.py            # Login, User, Role schemas
│   │   ├── student.py
│   │   ├── group.py
│   │   ├── contract.py
│   │   ├── transaction.py
│   │   ├── attendance.py
│   │   ├── report.py
│   │   ├── settings.py
│   │   └── public.py
│   ├── routers/
│   │   ├── auth.py            # POST /auth/login, GET /auth/me
│   │   ├── users.py           # User management
│   │   ├── roles.py           # Role & permission management
│   │   ├── students.py        # Student CRUD + nested resources
│   │   ├── groups.py          # Group CRUD
│   │   ├── contracts.py       # Contract CRUD
│   │   ├── transactions.py    # Transaction management
│   │   ├── coach.py           # Coach attendance marking
│   │   ├── gate.py            # Turnstile callback
│   │   ├── reports.py         # Dashboard & reports
│   │   ├── settings.py        # System settings
│   │   ├── public.py          # Public payment pages (no auth)
│   │   └── import_router.py   # Excel import
│   ├── services/
│   │   ├── debt.py            # Debt calculation logic
│   │   ├── payment.py         # Transaction operations
│   │   └── gate.py            # Gate entry processing
│   └── deps.py                # FastAPI dependencies (auth, RBAC)
├── alembic/
│   ├── versions/
│   └── env.py                 # Async migration config
├── main.py                    # FastAPI app entry point
├── seed.py                    # Database seeding script
├── requirements.txt
└── .env

```

## Core Concepts

### 1. RBAC (Role-Based Access Control)

**Dynamic Roles, Static Permissions**

- **Permissions** are static strings defined in `app/core/permissions.py`
- **Roles** are dynamic database entities that can have any combination of permissions
- **Super Admin** bypasses all permission checks (`is_super_admin=True`)

**Default Roles** (created by `seed.py`):
- Super Admin (all permissions)
- Director (view-only access to everything)
- Accountant (finance management)
- Coach (attendance marking)
- Admin (student & group management)

**How It Works**:
```python
# In routers:
@router.get("/transactions", dependencies=[Depends(require_permission(PERM_FINANCE_TRANSACTIONS_VIEW))])

# In deps.py:
def require_permission(permission_code: str):
    # Checks if user.is_super_admin OR permission exists in user.roles.permissions
```

### 2. Async SQLAlchemy

All database operations are async:

```python
async def get_student(student_id: int, db: AsyncSession):
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    return student
```

**Important**: Always use `await` with:
- `db.execute()`
- `db.commit()`
- `db.refresh()`

### 3. Business Logic Layer (Services)

Services contain reusable business logic:

- `services/debt.py`: Calculate student debt, check monthly payment
- `services/payment.py`: Manual transaction creation, assignment, cancellation
- `services/gate.py`: Turnstile entry processing (HARD-BLOCK logic)

**Example**:
```python
from app.services.debt import calculate_student_debt

debt = await calculate_student_debt(db, student_id)
```

### 4. Gate/Turnstile Logic

**HARD-BLOCK for students**:
- Turnstile POST to `/gate/callback` with `student_id` or `face_id`
- Backend checks if student paid for current month
- Returns `allowed=True/False` + reason
- Logs every entry attempt in `GateLog`

**SOFT-BLOCK for coaches**:
- Coach can mark attendance even if student has debt
- Warning shown in `/coach/sessions/{id}/students-with-debt-info`

### 5. Payment Flow

**Online Payments (Payme/Click)**:
- Parent uses `/public/contracts/{contract_number}` to check debt
- Initiates payment via `/public/payments/payme` or `/public/payments/click`
- Callback to `/payments/callback/payme` or `/payments/callback/click`
- Transaction created with `status=UNASSIGNED`
- Accountant assigns via `PATCH /transactions/{id}/assign`

**Offline Payments**:
- Accountant creates via `POST /transactions/manual` with `status=SUCCESS`

### 6. Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Environment Setup

1. Create `.env` from `.env.example`
2. Set `DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bunyodkor`
3. Set `SECRET_KEY` to a random string
4. Configure Payme/Click credentials (optional for now)

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Seed database
python seed.py

# Start server
uvicorn main:app --reload

# Or use main.py directly
python main.py
```

## API Response Format

**Success**:
```json
{
  "data": {...},
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

**Error**:
```json
{
  "detail": "Error message"
}
```

## Authentication

**Login**:
```bash
POST /auth/login
{
  "phone_or_email": "+998901234567",
  "password": "admin123"
}

Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Use Token**:
```
Authorization: Bearer <token>
```

## Common Development Tasks

### Adding a New Permission

1. Add to `app/core/permissions.py`:
```python
PERM_MY_NEW_FEATURE = "my:new:feature"
```

2. Add to `ALL_PERMISSIONS` list

3. Use in router:
```python
@router.get("/my-endpoint", dependencies=[Depends(require_permission(PERM_MY_NEW_FEATURE))])
```

### Adding a New Model

1. Create model in `app/models/`
2. Import in `app/models/__init__.py`
3. Create schemas in `app/schemas/`
4. Create migration: `alembic revision --autogenerate -m "add model"`
5. Apply: `alembic upgrade head`

### Debugging

- FastAPI auto-generates docs: `http://localhost:8000/docs`
- Check logs for SQL queries (set `echo=True` in `core/db.py`)

## Security Considerations

- Never commit `.env` file
- Change default admin password after first login
- Use strong `SECRET_KEY` in production
- Validate all user inputs (Pydantic does this automatically)
- SQL injection: protected by SQLAlchemy ORM
- XSS: handled by FastAPI's response serialization

## Testing

Currently no automated tests. Test manually via:
- `/docs` - Swagger UI
- Postman/Insomnia
- curl

## Future Enhancements

- [ ] Implement real Payme/Click integration
- [ ] Add SMS notifications
- [ ] Implement Excel import logic in `import_router.py`
- [ ] Add file upload for student photos
- [ ] WebSocket for real-time turnstile logs
- [ ] Background jobs (Celery/arq) for async tasks
