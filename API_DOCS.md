# BUNYODKOR CIMS - API Documentation for Frontend

**Base URL**: `http://localhost:8000`
**Swagger UI**: `http://localhost:8000/docs`
**ReDoc**: `http://localhost:8000/redoc`

## Authentication

All endpoints (except `/auth/login`, `/health`, and `/public/*`) require a Bearer token.

### Headers
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

---

## 1. AUTHENTICATION & AUTHORIZATION

### POST /auth/login
Login with phone/email and password.

**Request**:
```json
{
  "phone_or_email": "+998901234567",
  "password": "admin123"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### GET /auth/me
Get current user info with roles and permissions.

**Response**:
```json
{
  "user": {
    "id": 1,
    "phone": "+998901234567",
    "email": "admin@bunyodkor.uz",
    "full_name": "Super Admin",
    "is_super_admin": true,
    "status": "active",
    "created_at": "2025-01-15T10:00:00Z",
    "roles": [
      {
        "id": 1,
        "name": "Super Admin",
        "description": "Full system access"
      }
    ]
  },
  "permissions": [
    "finance:transactions:view",
    "students:view",
    "students:edit",
    ...
  ]
}
```

---

## 2. USER MANAGEMENT

### GET /users
List all users with pagination.

**Query Params**:
- `page` (default: 1)
- `page_size` (default: 20, max: 100)

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "phone": "+998901234567",
      "email": "admin@bunyodkor.uz",
      "full_name": "Super Admin",
      "is_super_admin": true,
      "status": "active",
      "created_at": "2025-01-15T10:00:00Z",
      "roles": [...]
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 50,
    "total_pages": 3
  }
}
```

### POST /users
Create a new user.

**Request**:
```json
{
  "phone": "+998901234568",
  "email": "coach@bunyodkor.uz",
  "full_name": "Coach Name",
  "password": "password123",
  "is_super_admin": false,
  "status": "active"
}
```

### PATCH /users/{user_id}
Update user details.

### PATCH /users/{user_id}/roles
Assign roles to a user.

**Request**:
```json
{
  "role_ids": [2, 3]
}
```

---

## 3. ROLES & PERMISSIONS

### GET /roles
List all roles with their permissions.

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "name": "Accountant",
      "description": "Financial management",
      "created_at": "2025-01-15T10:00:00Z",
      "permissions": [
        {
          "id": 1,
          "code": "finance:transactions:view",
          "description": "View financial transactions"
        }
      ]
    }
  ]
}
```

### POST /roles
Create a new role.

**Request**:
```json
{
  "name": "Custom Role",
  "description": "Custom permissions",
  "permission_ids": [1, 2, 5]
}
```

### PATCH /roles/{role_id}
Update role name/description/permissions.

### GET /roles/permissions
Get all available permissions (static list).

---

## 4. STUDENTS

### GET /students
List students with filters and pagination.

**Query Params**:
- `search` (search in first_name, last_name)
- `group_id`
- `status` (active, graduated, dropped, suspended)
- `page`, `page_size`

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "first_name": "Ali",
      "last_name": "Valiyev",
      "date_of_birth": "2010-05-15",
      "phone": "+998901111111",
      "address": "Tashkent, Yunusabad",
      "photo_url": "https://...",
      "face_id": "abc123",
      "status": "active",
      "group_id": 1,
      "created_at": "2025-01-10T08:00:00Z"
    }
  ],
  "meta": {...}
}
```

### POST /students
Create a student.

**Request**:
```json
{
  "first_name": "Ali",
  "last_name": "Valiyev",
  "date_of_birth": "2010-05-15",
  "phone": "+998901111111",
  "address": "Tashkent",
  "status": "active",
  "group_id": 1
}
```

### GET /students/{id}
Get single student details.

### PATCH /students/{id}
Update student.

### GET /students/{id}/contracts
List contracts for a student.

### GET /students/{id}/transactions
List transactions for a student.

### GET /students/{id}/attendance
List attendance records for a student.

### GET /students/{id}/gatelogs
List gate entry logs for a student.

---

## 5. GROUPS

### GET /groups
List all groups.

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "name": "U-12 Group A",
      "description": "Under 12 advanced group",
      "schedule_days": "Monday,Wednesday,Friday",
      "schedule_time": "16:00-18:00",
      "coach_id": 5,
      "created_at": "2025-01-05T10:00:00Z"
    }
  ],
  "meta": {...}
}
```

### POST /groups
Create a group.

### GET /groups/{id}
Get group details.

### PATCH /groups/{id}
Update group.

### GET /groups/{id}/students
List students in a group.

---

## 6. CONTRACTS

### GET /contracts
List contracts with filters.

**Query Params**:
- `status` (active, expired, terminated)
- `student_id`
- `page`, `page_size`

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "contract_number": "CNT-2025-001",
      "start_date": "2025-01-01",
      "end_date": "2025-12-31",
      "monthly_fee": 500000.0,
      "status": "active",
      "student_id": 1,
      "created_at": "2025-01-01T10:00:00Z"
    }
  ],
  "meta": {...}
}
```

### POST /contracts
Create a contract.

### PATCH /contracts/{id}
Update contract.

---

## 7. TRANSACTIONS

### GET /transactions
List transactions with filters.

**Query Params**:
- `from_date` (ISO datetime)
- `to_date` (ISO datetime)
- `status` (pending, success, failed, cancelled, unassigned)
- `source` (payme, click, bank, cash, manual)
- `student_id`
- `page`, `page_size`

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "external_id": "payme_12345",
      "amount": 500000.0,
      "source": "payme",
      "status": "success",
      "paid_at": "2025-01-15T14:30:00Z",
      "comment": null,
      "student_id": 1,
      "contract_id": 1,
      "created_by_user_id": 2,
      "created_at": "2025-01-15T14:30:00Z"
    }
  ],
  "meta": {...}
}
```

### GET /transactions/unassigned
List unassigned transactions (for accountant to assign).

### POST /transactions/manual
Create a manual transaction (cash/bank).

**Request**:
```json
{
  "amount": 500000.0,
  "source": "cash",
  "student_id": 1,
  "contract_id": 1,
  "comment": "Cash payment received",
  "paid_at": "2025-01-15T14:00:00Z"
}
```

### PATCH /transactions/{id}/assign
Assign an unassigned transaction to a student/contract.

**Request**:
```json
{
  "student_id": 1,
  "contract_id": 1
}
```

### PATCH /transactions/{id}/cancel
Cancel a transaction.

---

## 8. COACH ATTENDANCE

### GET /coach/groups
List groups assigned to the current coach.

### GET /coach/sessions?date=2025-01-15
List training sessions for a specific date (default: today).

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "session_date": "2025-01-15",
      "start_time": "16:00",
      "end_time": "18:00",
      "group_id": 1,
      "created_at": "2025-01-15T08:00:00Z"
    }
  ]
}
```

### GET /coach/sessions/{id}/students-with-debt-info
List students for a session with debt information.

**Response**:
```json
{
  "data": [
    {
      "student_id": 1,
      "first_name": "Ali",
      "last_name": "Valiyev",
      "has_debt": true,
      "debt_amount": 500000.0,
      "debt_warning": "Student owes 500000.0 UZS"
    }
  ]
}
```

**Important**: Coach can still mark attendance even if student has debt (SOFT-BLOCK).

### POST /coach/sessions/{id}/attendance
Mark attendance for a student.

**Request**:
```json
{
  "student_id": 1,
  "status": "present",
  "comment": "Good performance"
}
```

Status values: `present`, `absent`, `late`

---

## 9. GATE / TURNSTILE

### POST /gate/callback
Called by turnstile hardware to check entry permission.

**Request**:
```json
{
  "student_id": 1,
  "face_id": null
}
```

**Response**:
```json
{
  "allowed": false,
  "reason": "No payment for current month",
  "student_id": 1
}
```

Reasons:
- `OK` - Entry allowed
- `No payment for current month` - HARD-BLOCK
- `Student not found`

### GET /gate/logs
View gate entry logs.

**Query Params**:
- `from_date`, `to_date`
- `student_id`
- `allowed` (true/false)
- `page`, `page_size`

---

## 10. REPORTS

### GET /reports/dashboard/summary
Quick dashboard stats.

**Response**:
```json
{
  "data": {
    "today_revenue": 2500000.0,
    "active_students": 150,
    "total_debtors": 12,
    "today_sessions": 8
  }
}
```

### GET /reports/finance?from_date=2025-01-01&to_date=2025-01-31
Financial report with breakdown by payment source.

**Response**:
```json
{
  "data": {
    "from_date": "2025-01-01",
    "to_date": "2025-01-31",
    "total_revenue": 75000000.0,
    "breakdown": [
      {
        "source": "payme",
        "total_amount": 50000000.0,
        "transaction_count": 100
      },
      {
        "source": "cash",
        "total_amount": 25000000.0,
        "transaction_count": 50
      }
    ]
  }
}
```

### GET /reports/attendance/groups
Attendance percentage by groups.

### GET /reports/attendance/students/{id}
Attendance report for a specific student.

### GET /reports/debtors
List of students with outstanding debts.

**Query Params**:
- `group_id`
- `min_debt_amount`
- `page`, `page_size`

**Response**:
```json
{
  "data": [
    {
      "student_id": 1,
      "student_name": "Ali Valiyev",
      "contract_number": "CNT-2025-001",
      "debt_amount": 1500000.0,
      "group_name": "U-12 Group A"
    }
  ],
  "meta": {...}
}
```

---

## 11. SETTINGS

### GET /settings/system
Get all system settings.

### PATCH /settings/system
Update system settings.

**Request**:
```json
{
  "payme_merchant_id": "12345",
  "sms_api_key": "abc123"
}
```

---

## 12. PUBLIC (NO AUTH)

### GET /public/contracts/{contract_number}
Get contract info by contract number (for parents).

**Response**:
```json
{
  "contract_number": "CNT-2025-001",
  "student_first_name": "Ali",
  "student_last_name": "Valiyev",
  "monthly_fee": 500000.0,
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "current_debt": 500000.0,
  "last_payment_date": "2024-12-15"
}
```

### POST /public/payments/payme
Initiate Payme payment.

**Request**:
```json
{
  "contract_number": "CNT-2025-001",
  "amount": 500000.0
}
```

### POST /public/payments/click
Initiate Click payment.

### POST /payments/callback/payme
Payme server callback (internal use).

### POST /payments/callback/click
Click server callback (internal use).

---

## 13. IMPORT

### POST /import/students
Upload Excel file to import students.

**Request**: `multipart/form-data` with file upload

### GET /import/students/result
Get results of last import operation.

---

## Common Response Formats

### Success with Data
```json
{
  "data": {...},
  "meta": null
}
```

### Success with Pagination
```json
{
  "data": [...],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### Error
```json
{
  "detail": "Permission denied: finance:transactions:view"
}
```

HTTP Status Codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (no permission)
- `404` - Not Found
- `500` - Internal Server Error

---

## Permissions Required

| Endpoint | Permission |
|----------|-----------|
| `/users/*` | `users:manage` |
| `/roles/*` | `roles:manage` |
| `/students` (GET) | `students:view` |
| `/students` (POST/PATCH) | `students:edit` |
| `/groups` (GET) | `groups:view` |
| `/groups` (POST/PATCH) | `groups:edit` |
| `/contracts/*` | `contracts:view`, `contracts:edit` |
| `/transactions` (GET) | `finance:transactions:view` |
| `/transactions/manual` | `finance:transactions:manual` |
| `/transactions/*/assign` | `finance:unassigned:assign` |
| `/coach/*` | `attendance:coach:mark` |
| `/gate/logs` | `gate:logs:view` |
| `/reports/dashboard` | `reports:dashboard:view` |
| `/reports/finance` | `reports:finance:view` |
| `/reports/attendance` | `reports:attendance:view` |
| `/settings/system` (GET) | `settings:system:view` |
| `/settings/system` (PATCH) | `settings:system:edit` |

**Note**: Super admins bypass all permission checks.

---

## Testing Credentials

After running `python seed.py`:

**Super Admin**:
- Phone: `+998901234567`
- Password: `admin123`

**⚠️ Change password immediately in production!**
