# Bunyodkor FastAPI - Complete API Documentation

## Table of Contents
1. [Authentication](#authentication)
2. [Users](#users)
3. [Students](#students)
4. [Coaches](#coaches)
5. [Contracts](#contracts)
6. [Transactions](#transactions)
7. [Groups](#groups)
8. [Roles & Permissions](#roles--permissions)

---

## Base URL
```
http://127.0.0.1:8000
```

## Authentication
All authenticated endpoints require a Bearer token in the Authorization header:
```
Authorization: Bearer <your_token_here>
```

---

## 1. Authentication

### 1.1 Login
**Endpoint:** `POST /auth/login`

**Description:** Login with phone/email and password to receive an access token.

**Request Body:**
```json
{
  "phone_or_email": "998901234567",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:**
- `401 Unauthorized`: Incorrect phone/email or password

---

### 1.2 Register
**Endpoint:** `POST /auth/register`

**Description:** Register a new user account.

**Request Body:**
```json
{
  "phone": "998901234567",
  "email": "user@example.com",
  "full_name": "John Doe",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "id": 1,
  "phone": "998901234567",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_super_admin": false,
  "status": "ACTIVE",
  "created_at": "2025-12-02T10:00:00Z"
}
```

**Errors:**
- `400 Bad Request`: Phone number already registered
- `400 Bad Request`: Email already registered

---

### 1.3 Get Current User Info
**Endpoint:** `GET /auth/me`

**Description:** Get currently authenticated user information with roles and permissions.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "user": {
    "id": 1,
    "phone": "998901234567",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_super_admin": false,
    "status": "ACTIVE",
    "created_at": "2025-12-02T10:00:00Z",
    "roles": [
      {
        "id": 1,
        "name": "Coach",
        "description": "Teacher role"
      }
    ]
  },
  "permissions": ["attendance:coach:mark", "groups:view"]
}
```

---

## 2. Users

### 2.1 Get All Users
**Endpoint:** `GET /users`

**Permission Required:** `users:manage`

**Query Parameters:**
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "phone": "998901234567",
      "email": "user@example.com",
      "full_name": "John Doe",
      "is_super_admin": false,
      "status": "ACTIVE",
      "created_at": "2025-12-02T10:00:00Z",
      "roles": [
        {
          "id": 1,
          "name": "Coach",
          "description": "Teacher role"
        }
      ]
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

---

### 2.2 Get Coaches List
**Endpoint:** `GET /users/coaches`

**Authentication Required:** Yes (any authenticated user)

**Description:** Returns all users with "Coach" role and their assigned groups.

**Response:**
```json
{
  "data": [
    {
      "id": 5,
      "phone": "998901234567",
      "email": "coach@example.com",
      "full_name": "Jane Coach",
      "is_super_admin": false,
      "status": "ACTIVE",
      "created_at": "2025-12-02T10:00:00Z",
      "groups": [
        {
          "id": 1,
          "name": "Python Beginners",
          "description": "Beginner Python course",
          "coach_id": 5,
          "created_at": "2025-12-02T10:00:00Z"
        }
      ]
    }
  ]
}
```

---

### 2.3 Create User
**Endpoint:** `POST /users`

**Permission Required:** `users:manage`

**Request Body:**
```json
{
  "phone": "998901234567",
  "email": "newuser@example.com",
  "full_name": "New User",
  "password": "password123",
  "is_super_admin": false,
  "status": "ACTIVE"
}
```

**Response:**
```json
{
  "data": {
    "id": 10,
    "phone": "998901234567",
    "email": "newuser@example.com",
    "full_name": "New User",
    "is_super_admin": false,
    "status": "ACTIVE",
    "created_at": "2025-12-02T11:00:00Z"
  }
}
```

**Errors:**
- `400 Bad Request`: Phone already registered
- `400 Bad Request`: This email is already registered

---

### 2.4 Get User by ID
**Endpoint:** `GET /users/{user_id}`

**Permission Required:** `users:manage`

**Path Parameters:**
- `user_id` (integer) - User ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "phone": "998901234567",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_super_admin": false,
    "status": "ACTIVE",
    "created_at": "2025-12-02T10:00:00Z",
    "roles": [
      {
        "id": 1,
        "name": "Coach"
      }
    ]
  }
}
```

**Errors:**
- `404 Not Found`: User not found

---

### 2.5 Update User
**Endpoint:** `PATCH /users/{user_id}`

**Permission Required:** `users:manage`

**Path Parameters:**
- `user_id` (integer) - User ID

**Request Body:** (all fields optional)
```json
{
  "phone": "998901234568",
  "email": "updated@example.com",
  "full_name": "Updated Name",
  "password": "newpassword123",
  "status": "INACTIVE"
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "phone": "998901234568",
    "email": "updated@example.com",
    "full_name": "Updated Name",
    "is_super_admin": false,
    "status": "INACTIVE",
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: User not found
- `400 Bad Request`: Phone already registered
- `400 Bad Request`: This email is already registered

---

### 2.6 Update User Roles
**Endpoint:** `PATCH /users/{user_id}/roles`

**Permission Required:** `users:manage`

**Path Parameters:**
- `user_id` (integer) - User ID

**Request Body:**
```json
{
  "role_ids": [1, 2, 3]
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "phone": "998901234567",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_super_admin": false,
    "status": "ACTIVE",
    "created_at": "2025-12-02T10:00:00Z",
    "roles": [
      {
        "id": 1,
        "name": "Coach"
      },
      {
        "id": 2,
        "name": "Admin"
      }
    ]
  }
}
```

**Errors:**
- `404 Not Found`: User not found
- `400 Bad Request`: One or more role IDs are invalid

---

### 2.7 Delete User
**Endpoint:** `DELETE /users/{user_id}`

**Permission Required:** `users:manage`

**Path Parameters:**
- `user_id` (integer) - User ID

**Response:**
```json
{
  "data": {
    "message": "User deleted successfully"
  }
}
```

**Errors:**
- `404 Not Found`: User not found
- `400 Bad Request`: Cannot delete super admin user

---

## 3. Students

### 3.1 Search Students
**Endpoint:** `GET /students/search`

**Permission Required:** `students:view`

**Description:** Comprehensive search across multiple fields: first name, last name, contract number, phone, and parent email.

**Query Parameters:**
- `query` (string, required) - Search term
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Example Request:**
```
GET /students/search?query=John&page=1&page_size=20
```

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "first_name": "John",
      "last_name": "Smith",
      "date_of_birth": "2010-05-15",
      "phone": "998901234567",
      "address": "123 Main St",
      "photo_url": "https://example.com/photo.jpg",
      "face_id": "FACE123456",
      "status": "ACTIVE",
      "group_id": 1,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

---

### 3.2 Get All Students
**Endpoint:** `GET /students`

**Permission Required:** `students:view`

**Query Parameters:**
- `search` (string, optional) - Search by first or last name
- `group_id` (integer, optional) - Filter by group
- `status` (string, optional) - Filter by status (ACTIVE, INACTIVE, GRADUATED, EXPELLED)
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "first_name": "John",
      "last_name": "Smith",
      "date_of_birth": "2010-05-15",
      "phone": "998901234567",
      "address": "123 Main St",
      "photo_url": null,
      "face_id": "FACE123",
      "status": "ACTIVE",
      "group_id": 1,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

---

### 3.3 Get Unpaid Students
**Endpoint:** `GET /students/unpaid`

**Permission Required:** `students:view`

**Description:** Get students who haven't paid for a specific month. Defaults to current month.

**Query Parameters:**
- `year` (integer, optional) - Target year (defaults to current year)
- `month` (integer, optional, 1-12) - Target month (defaults to current month)
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Example Request:**
```
GET /students/unpaid?year=2025&month=12&page=1&page_size=20
```

**Response:**
```json
{
  "data": [
    {
      "student": {
        "id": 1,
        "first_name": "John",
        "last_name": "Smith",
        "date_of_birth": "2010-05-15",
        "phone": "998901234567",
        "status": "ACTIVE",
        "group_id": 1,
        "created_at": "2025-12-02T10:00:00Z"
      },
      "total_expected": 500000,
      "total_paid": 200000,
      "debt_amount": 300000,
      "active_contracts_count": 1
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 25,
    "total_pages": 2
  }
}
```

---

### 3.4 Get Student Full Info
**Endpoint:** `GET /students/fullinfo/{student_id}`

**Permission Required:** `students:view`

**Description:** Get complete student information including contracts, group, coach, payments, and attendance.

**Path Parameters:**
- `student_id` (integer) - Student ID

**Response:**
```json
{
  "data": {
    "student": {
      "id": 1,
      "first_name": "John",
      "last_name": "Smith",
      "date_of_birth": "2010-05-15",
      "phone": "998901234567",
      "status": "ACTIVE",
      "group_id": 1,
      "created_at": "2025-12-02T10:00:00Z"
    },
    "parents": [
      {
        "id": 1,
        "first_name": "Jane",
        "last_name": "Smith",
        "phone": "998901234567",
        "email": "parent@example.com",
        "relationship_type": "Mother",
        "student_id": 1,
        "created_at": "2025-12-02T10:00:00Z"
      }
    ],
    "contracts": [
      {
        "id": 1,
        "contract_number": "CON-2025-001",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "monthly_fee": 500000,
        "status": "ACTIVE",
        "student_id": 1,
        "created_at": "2025-12-02T10:00:00Z"
      }
    ],
    "group": {
      "id": 1,
      "name": "Python Beginners",
      "description": "Beginner Python course",
      "coach_id": 5,
      "created_at": "2025-12-02T10:00:00Z"
    },
    "coach": {
      "id": 5,
      "phone": "998901234567",
      "email": "coach@example.com",
      "full_name": "Jane Coach",
      "status": "ACTIVE"
    },
    "transactions": [
      {
        "id": 1,
        "amount": 500000,
        "source": "CASH",
        "status": "SUCCESS",
        "paid_at": "2025-12-01T10:00:00Z",
        "payment_year": 2025,
        "payment_months": [12],
        "student_id": 1,
        "contract_id": 1,
        "created_at": "2025-12-01T10:00:00Z"
      }
    ],
    "attendances": [
      {
        "id": 1,
        "session_id": 1,
        "student_id": 1,
        "status": "PRESENT",
        "comment": null,
        "marked_by_user_id": 5,
        "created_at": "2025-12-02T10:00:00Z"
      }
    ]
  }
}
```

**Errors:**
- `404 Not Found`: Student not found

---

### 3.5 Create Student
**Endpoint:** `POST /students`

**Permission Required:** `students:edit`

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "2010-05-15",
  "phone": "998901234567",
  "address": "123 Main St",
  "photo_url": "https://example.com/photo.jpg",
  "face_id": "FACE123456",
  "status": "ACTIVE",
  "group_id": 1
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "first_name": "John",
    "last_name": "Smith",
    "date_of_birth": "2010-05-15",
    "phone": "998901234567",
    "address": "123 Main St",
    "photo_url": "https://example.com/photo.jpg",
    "face_id": "FACE123456",
    "status": "ACTIVE",
    "group_id": 1,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `400 Bad Request`: Face ID already exists. Please use a unique Face ID
- `404 Not Found`: Group with ID {group_id} not found

---

### 3.6 Get Student by ID
**Endpoint:** `GET /students/{student_id}`

**Permission Required:** `students:view`

**Path Parameters:**
- `student_id` (integer) - Student ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "first_name": "John",
    "last_name": "Smith",
    "date_of_birth": "2010-05-15",
    "phone": "998901234567",
    "status": "ACTIVE",
    "group_id": 1,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Student not found

---

### 3.7 Update Student
**Endpoint:** `PATCH /students/{student_id}`

**Permission Required:** `students:edit`

**Path Parameters:**
- `student_id` (integer) - Student ID

**Request Body:** (all fields optional)
```json
{
  "first_name": "John",
  "last_name": "Smith",
  "phone": "998901234568",
  "status": "GRADUATED",
  "group_id": 2
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "first_name": "John",
    "last_name": "Smith",
    "date_of_birth": "2010-05-15",
    "phone": "998901234568",
    "status": "GRADUATED",
    "group_id": 2,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Student not found
- `400 Bad Request`: Face ID already exists. Please use a unique Face ID
- `404 Not Found`: Group with ID {group_id} not found

---

### 3.8 Get Student Contracts
**Endpoint:** `GET /students/{student_id}/contracts`

**Permission Required:** `students:view`

**Path Parameters:**
- `student_id` (integer) - Student ID

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "contract_number": "CON-2025-001",
      "start_date": "2025-01-01",
      "end_date": "2025-12-31",
      "monthly_fee": 500000,
      "status": "ACTIVE",
      "student_id": 1,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ]
}
```

---

### 3.9 Get Student Transactions
**Endpoint:** `GET /students/{student_id}/transactions`

**Permission Required:** `students:view`

**Path Parameters:**
- `student_id` (integer) - Student ID

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "amount": 500000,
      "source": "CASH",
      "status": "SUCCESS",
      "paid_at": "2025-12-01T10:00:00Z",
      "payment_year": 2025,
      "payment_months": [12],
      "student_id": 1,
      "contract_id": 1,
      "created_at": "2025-12-01T10:00:00Z"
    }
  ]
}
```

---

### 3.10 Get Student Attendance
**Endpoint:** `GET /students/{student_id}/attendance`

**Permission Required:** `students:view`

**Path Parameters:**
- `student_id` (integer) - Student ID

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "session_id": 1,
      "student_id": 1,
      "status": "PRESENT",
      "comment": null,
      "marked_by_user_id": 5,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ]
}
```

---

### 3.11 Delete Student
**Endpoint:** `DELETE /students/{student_id}`

**Permission Required:** `students:edit`

**Path Parameters:**
- `student_id` (integer) - Student ID

**Response:**
```json
{
  "data": {
    "message": "Student deleted successfully"
  }
}
```

**Errors:**
- `404 Not Found`: Student not found

---

## 4. Coaches

### 4.1 Get Coach's Groups
**Endpoint:** `GET /coach/groups`

**Permission Required:** `attendance:coach:mark`

**Description:** Get all groups assigned to the authenticated coach.

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "name": "Python Beginners",
      "description": "Beginner Python course",
      "coach_id": 5,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ]
}
```

---

### 4.2 Get Coach's Sessions
**Endpoint:** `GET /coach/sessions`

**Permission Required:** `attendance:coach:mark`

**Description:** Get sessions for the authenticated coach. Defaults to today's sessions.

**Query Parameters:**
- `date` (date, optional) - Filter by specific date (format: YYYY-MM-DD)

**Example Request:**
```
GET /coach/sessions?date=2025-12-02
```

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "session_date": "2025-12-02",
      "topic": "Introduction to Python",
      "start_time": "10:00",
      "end_time": "12:00",
      "group_id": 1,
      "created_by_user_id": 5,
      "created_at": "2025-12-02T09:00:00Z"
    }
  ]
}
```

---

### 4.3 Create Session (Lesson)
**Endpoint:** `POST /coach/sessions`

**Permission Required:** `attendance:coach:mark`

**Description:** Create a new lesson/session for a group.

**Request Body:**
```json
{
  "session_date": "2025-12-02",
  "topic": "Introduction to Python",
  "start_time": "10:00",
  "end_time": "12:00",
  "group_id": 1
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "session_date": "2025-12-02",
    "topic": "Introduction to Python",
    "start_time": "10:00",
    "end_time": "12:00",
    "group_id": 1,
    "created_by_user_id": 5,
    "created_at": "2025-12-02T09:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Group not found or you do not have permission to create sessions for this group

---

### 4.4 Get Session Details
**Endpoint:** `GET /coach/sessions/{session_id}`

**Permission Required:** `attendance:coach:mark`

**Description:** Get session details with all attendance records.

**Path Parameters:**
- `session_id` (integer) - Session ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "session_date": "2025-12-02",
    "topic": "Introduction to Python",
    "start_time": "10:00",
    "end_time": "12:00",
    "group_id": 1,
    "created_by_user_id": 5,
    "created_at": "2025-12-02T09:00:00Z",
    "attendances": [
      {
        "id": 1,
        "session_id": 1,
        "student_id": 1,
        "status": "PRESENT",
        "comment": null,
        "marked_by_user_id": 5,
        "created_at": "2025-12-02T10:00:00Z"
      }
    ]
  }
}
```

**Errors:**
- `404 Not Found`: Session not found or you do not have permission to view it

---

### 4.5 Mark Single Attendance
**Endpoint:** `POST /coach/sessions/{session_id}/attendance`

**Permission Required:** `attendance:coach:mark`

**Description:** Mark attendance for a single student.

**Path Parameters:**
- `session_id` (integer) - Session ID

**Request Body:**
```json
{
  "student_id": 1,
  "status": "PRESENT",
  "comment": "On time"
}
```

**Status values:** `PRESENT`, `ABSENT`, `LATE`

**Response:**
```json
{
  "data": {
    "message": "Attendance marked successfully",
    "attendance_id": 1
  }
}
```

**Errors:**
- `404 Not Found`: Session not found
- `404 Not Found`: Student with ID {student_id} not found

---

### 4.6 Mark Bulk Attendance
**Endpoint:** `POST /coach/sessions/{session_id}/bulk-attendance`

**Permission Required:** `attendance:coach:mark`

**Description:** Mark attendance for multiple students at once.

**Path Parameters:**
- `session_id` (integer) - Session ID

**Request Body:**
```json
{
  "session_id": 1,
  "attendances": [
    {
      "student_id": 1,
      "status": "PRESENT",
      "comment": "On time"
    },
    {
      "student_id": 2,
      "status": "LATE",
      "comment": "Arrived 10 minutes late"
    },
    {
      "student_id": 3,
      "status": "ABSENT",
      "comment": null
    }
  ]
}
```

**Response:**
```json
{
  "data": {
    "message": "Successfully marked attendance for 3 students",
    "count": 3
  }
}
```

**Errors:**
- `404 Not Found`: Session not found or you do not have permission to mark attendance
- `400 Bad Request`: Session ID mismatch
- `404 Not Found`: Student with ID {student_id} not found

---

### 4.7 Get Group Attendance Statistics
**Endpoint:** `GET /coach/groups/{group_id}/attendance-stats`

**Permission Required:** `attendance:coach:mark`

**Description:** Get attendance statistics for a group.

**Path Parameters:**
- `group_id` (integer) - Group ID

**Query Parameters:**
- `from_date` (date, optional) - Start date for statistics
- `to_date` (date, optional) - End date for statistics

**Example Request:**
```
GET /coach/groups/1/attendance-stats?from_date=2025-11-01&to_date=2025-12-02
```

**Response:**
```json
{
  "data": {
    "total_sessions": 20,
    "present_count": 150,
    "absent_count": 10,
    "late_count": 5,
    "attendance_rate": 90.91
  }
}
```

**Errors:**
- `404 Not Found`: Group not found or you do not have permission to view statistics

---

### 4.8 Get Student Attendance Statistics
**Endpoint:** `GET /coach/students/{student_id}/attendance-stats`

**Permission Required:** `attendance:coach:mark`

**Description:** Get attendance statistics for a specific student.

**Path Parameters:**
- `student_id` (integer) - Student ID

**Query Parameters:**
- `from_date` (date, optional) - Start date for statistics
- `to_date` (date, optional) - End date for statistics

**Response:**
```json
{
  "data": {
    "total_sessions": 20,
    "present_count": 18,
    "absent_count": 1,
    "late_count": 1,
    "attendance_rate": 90.0
  }
}
```

**Errors:**
- `404 Not Found`: Student not found or not in your groups

---

## 5. Contracts

### 5.1 Get All Contracts
**Endpoint:** `GET /contracts`

**Permission Required:** `contracts:view`

**Query Parameters:**
- `status` (string, optional) - Filter by status (ACTIVE, COMPLETED, CANCELLED)
- `student_id` (integer, optional) - Filter by student
- `contract_number` (string, optional) - Search by contract number
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Example Request:**
```
GET /contracts?status=ACTIVE&student_id=1&page=1&page_size=20
```

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "contract_number": "CON-2025-001",
      "start_date": "2025-01-01",
      "end_date": "2025-12-31",
      "monthly_fee": 500000,
      "status": "ACTIVE",
      "student_id": 1,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

---

### 5.2 Create Contract
**Endpoint:** `POST /contracts`

**Permission Required:** `contracts:edit`

**Description:** Create a new contract. A student can only have one active contract at a time.

**Request Body:**
```json
{
  "contract_number": "CON-2025-001",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "monthly_fee": 500000,
  "status": "ACTIVE",
  "student_id": 1
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "contract_number": "CON-2025-001",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "monthly_fee": 500000,
    "status": "ACTIVE",
    "student_id": 1,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Student with ID {student_id} not found
- `400 Bad Request`: This contract already exists
- `400 Bad Request`: This student already has an active contract. A student can only have one active contract at a time

---

### 5.3 Get Contract by ID
**Endpoint:** `GET /contracts/{contract_id}`

**Permission Required:** `contracts:view`

**Path Parameters:**
- `contract_id` (integer) - Contract ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "contract_number": "CON-2025-001",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "monthly_fee": 500000,
    "status": "ACTIVE",
    "student_id": 1,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Contract not found

---

### 5.4 Update Contract
**Endpoint:** `PATCH /contracts/{contract_id}`

**Permission Required:** `contracts:edit`

**Path Parameters:**
- `contract_id` (integer) - Contract ID

**Request Body:** (all fields optional)
```json
{
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "monthly_fee": 600000,
  "status": "COMPLETED"
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "contract_number": "CON-2025-001",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "monthly_fee": 600000,
    "status": "COMPLETED",
    "student_id": 1,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Contract not found
- `400 Bad Request`: This contract already exists (if updating contract_number)
- `400 Bad Request`: This student already has an active contract. A student can only have one active contract at a time

---

### 5.5 Delete Contract
**Endpoint:** `DELETE /contracts/{contract_id}`

**Permission Required:** `contracts:edit`

**Path Parameters:**
- `contract_id` (integer) - Contract ID

**Response:**
```json
{
  "data": {
    "message": "Contract deleted successfully"
  }
}
```

**Errors:**
- `404 Not Found`: Contract not found

---

## 6. Transactions

### 6.1 Get All Transactions
**Endpoint:** `GET /transactions`

**Permission Required:** `finance:transactions:view`

**Query Parameters:**
- `from_date` (datetime, optional) - Filter from date
- `to_date` (datetime, optional) - Filter to date
- `status` (string, optional) - Filter by status (SUCCESS, PENDING, FAILED, CANCELLED, UNASSIGNED)
- `source` (string, optional) - Filter by source (CASH, CARD, BANK_TRANSFER, ONLINE, PAYME, CLICK, UZUM)
- `student_id` (integer, optional) - Filter by student
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Example Request:**
```
GET /transactions?status=SUCCESS&from_date=2025-11-01T00:00:00Z&to_date=2025-12-02T23:59:59Z&page=1
```

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "external_id": "PAY123456",
      "amount": 500000,
      "source": "CASH",
      "status": "SUCCESS",
      "paid_at": "2025-12-01T10:00:00Z",
      "comment": "December payment",
      "payment_year": 2025,
      "payment_months": [12],
      "student_id": 1,
      "contract_id": 1,
      "created_by_user_id": 5,
      "created_at": "2025-12-01T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

### 6.2 Get Unassigned Transactions
**Endpoint:** `GET /transactions/unassigned`

**Permission Required:** `finance:unassigned:view`

**Description:** Get all transactions that haven't been assigned to a student yet.

**Query Parameters:**
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Response:**
```json
{
  "data": [
    {
      "id": 10,
      "external_id": "PAY789012",
      "amount": 500000,
      "source": "PAYME",
      "status": "UNASSIGNED",
      "paid_at": "2025-12-01T10:00:00Z",
      "student_id": null,
      "contract_id": null,
      "created_at": "2025-12-01T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

---

### 6.3 Get Transaction by ID
**Endpoint:** `GET /transactions/{transaction_id}`

**Permission Required:** `finance:transactions:view`

**Path Parameters:**
- `transaction_id` (integer) - Transaction ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "amount": 500000,
    "source": "CASH",
    "status": "SUCCESS",
    "paid_at": "2025-12-01T10:00:00Z",
    "payment_year": 2025,
    "payment_months": [12],
    "student_id": 1,
    "contract_id": 1,
    "created_at": "2025-12-01T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Transaction not found

---

### 6.4 Create Manual Transaction
**Endpoint:** `POST /transactions/manual`

**Permission Required:** `finance:transactions:manual`

**Description:** Create a manual transaction for a student using their contract number.

**Request Body:**
```json
{
  "amount": 500000,
  "source": "CASH",
  "contract_number": "CON-2025-001",
  "payment_year": 2025,
  "payment_months": [12, 1, 2],
  "comment": "Payment for December, January, February",
  "paid_at": "2025-12-01T10:00:00Z"
}
```

**Payment Sources:** `CASH`, `CARD`, `BANK_TRANSFER`, `ONLINE`, `PAYME`, `CLICK`, `UZUM`

**Payment Months:** Array of integers from 1 to 12 representing months

**Response:**
```json
{
  "data": {
    "id": 1,
    "amount": 500000,
    "source": "CASH",
    "status": "SUCCESS",
    "paid_at": "2025-12-01T10:00:00Z",
    "comment": "Payment for December, January, February",
    "payment_year": 2025,
    "payment_months": [12, 1, 2],
    "student_id": 1,
    "contract_id": 1,
    "created_by_user_id": 5,
    "created_at": "2025-12-01T10:00:00Z"
  }
}
```

**Errors:**
- `400 Bad Request`: Contract with number '{contract_number}' not found
- `400 Bad Request`: Invalid month: {month}. Must be between 1 and 12

---

### 6.5 Assign Transaction
**Endpoint:** `PATCH /transactions/{transaction_id}/assign`

**Permission Required:** `finance:unassigned:assign`

**Description:** Assign an unassigned transaction to a student and contract.

**Path Parameters:**
- `transaction_id` (integer) - Transaction ID

**Request Body:**
```json
{
  "student_id": 1,
  "contract_id": 1
}
```

**Response:**
```json
{
  "data": {
    "id": 10,
    "amount": 500000,
    "source": "PAYME",
    "status": "SUCCESS",
    "student_id": 1,
    "contract_id": 1,
    "created_at": "2025-12-01T10:00:00Z"
  }
}
```

**Errors:**
- `400 Bad Request`: Transaction not found or not in UNASSIGNED status
- `400 Bad Request`: Student not found
- `400 Bad Request`: Contract not found

---

### 6.6 Cancel Transaction
**Endpoint:** `PATCH /transactions/{transaction_id}/cancel`

**Permission Required:** `finance:transactions:cancel`

**Description:** Cancel a transaction.

**Path Parameters:**
- `transaction_id` (integer) - Transaction ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "amount": 500000,
    "source": "CASH",
    "status": "CANCELLED",
    "created_at": "2025-12-01T10:00:00Z"
  }
}
```

**Errors:**
- `400 Bad Request`: Transaction not found

---

### 6.7 Delete Transaction
**Endpoint:** `DELETE /transactions/{transaction_id}`

**Permission Required:** `finance:transactions:cancel`

**Path Parameters:**
- `transaction_id` (integer) - Transaction ID

**Response:**
```json
{
  "data": {
    "message": "Transaction deleted successfully"
  }
}
```

**Errors:**
- `404 Not Found`: Transaction not found

---

## 7. Groups

### 7.1 Get All Groups
**Endpoint:** `GET /groups`

**Permission Required:** `groups:view`

**Query Parameters:**
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "name": "Python Beginners",
      "description": "Beginner Python course",
      "coach_id": 5,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 10,
    "total_pages": 1
  }
}
```

---

### 7.2 Create Group
**Endpoint:** `POST /groups`

**Permission Required:** `groups:edit`

**Request Body:**
```json
{
  "name": "Python Advanced",
  "description": "Advanced Python programming",
  "coach_id": 5
}
```

**Response:**
```json
{
  "data": {
    "id": 2,
    "name": "Python Advanced",
    "description": "Advanced Python programming",
    "coach_id": 5,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Coach with ID {coach_id} not found

---

### 7.3 Get Group by ID
**Endpoint:** `GET /groups/{group_id}`

**Permission Required:** `groups:view`

**Path Parameters:**
- `group_id` (integer) - Group ID

**Response:**
```json
{
  "data": {
    "id": 1,
    "name": "Python Beginners",
    "description": "Beginner Python course",
    "coach_id": 5,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Group not found

---

### 7.4 Update Group
**Endpoint:** `PATCH /groups/{group_id}`

**Permission Required:** `groups:edit`

**Path Parameters:**
- `group_id` (integer) - Group ID

**Request Body:** (all fields optional)
```json
{
  "name": "Python Intermediate",
  "description": "Intermediate Python programming",
  "coach_id": 6
}
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "name": "Python Intermediate",
    "description": "Intermediate Python programming",
    "coach_id": 6,
    "created_at": "2025-12-02T10:00:00Z"
  }
}
```

**Errors:**
- `404 Not Found`: Group not found
- `404 Not Found`: Coach with ID {coach_id} not found

---

### 7.5 Get Group Students
**Endpoint:** `GET /groups/{group_id}/students`

**Permission Required:** `groups:view`

**Description:** Get all students in a specific group.

**Path Parameters:**
- `group_id` (integer) - Group ID

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "first_name": "John",
      "last_name": "Smith",
      "date_of_birth": "2010-05-15",
      "phone": "998901234567",
      "status": "ACTIVE",
      "group_id": 1,
      "created_at": "2025-12-02T10:00:00Z"
    }
  ]
}
```

---

### 7.6 Delete Group
**Endpoint:** `DELETE /groups/{group_id}`

**Permission Required:** `groups:edit`

**Path Parameters:**
- `group_id` (integer) - Group ID

**Response:**
```json
{
  "data": {
    "message": "Group deleted successfully"
  }
}
```

**Errors:**
- `404 Not Found`: Group not found

---

## 8. Roles & Permissions

### 8.1 Get All Roles
**Endpoint:** `GET /roles`

**Permission Required:** `roles:manage`

**Description:** Get all roles with their associated permissions.

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "name": "Coach",
      "description": "Teacher role",
      "permissions": [
        {
          "id": 1,
          "code": "attendance:coach:mark",
          "name": "Mark Attendance",
          "description": "Can mark student attendance"
        },
        {
          "id": 2,
          "code": "groups:view",
          "name": "View Groups",
          "description": "Can view groups"
        }
      ]
    }
  ]
}
```

---

### 8.2 Create Role
**Endpoint:** `POST /roles`

**Permission Required:** `roles:manage`

**Request Body:**
```json
{
  "name": "Admin",
  "description": "Administrator role",
  "permission_ids": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "data": {
    "id": 2,
    "name": "Admin",
    "description": "Administrator role",
    "permissions": [
      {
        "id": 1,
        "code": "attendance:coach:mark",
        "name": "Mark Attendance"
      }
    ]
  }
}
```

---

### 8.3 Update Role
**Endpoint:** `PATCH /roles/{role_id}`

**Permission Required:** `roles:manage`

**Path Parameters:**
- `role_id` (integer) - Role ID

**Request Body:** (all fields optional)
```json
{
  "name": "Senior Admin",
  "description": "Senior administrator role",
  "permission_ids": [1, 2, 3, 4, 5, 6, 7]
}
```

**Response:**
```json
{
  "data": {
    "id": 2,
    "name": "Senior Admin",
    "description": "Senior administrator role",
    "permissions": [
      {
        "id": 1,
        "code": "attendance:coach:mark",
        "name": "Mark Attendance"
      }
    ]
  }
}
```

**Errors:**
- `404 Not Found`: Role not found

---

### 8.4 Delete Role
**Endpoint:** `DELETE /roles/{role_id}`

**Permission Required:** `roles:manage`

**Path Parameters:**
- `role_id` (integer) - Role ID

**Response:**
```json
{
  "data": {
    "message": "Role deleted successfully"
  }
}
```

**Errors:**
- `404 Not Found`: Role not found

---

### 8.5 Get All Permissions
**Endpoint:** `GET /roles/permissions`

**Description:** Get list of all available permissions in the system.

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "code": "users:manage",
      "name": "Manage Users",
      "description": "Can create, update, and delete users"
    },
    {
      "id": 2,
      "code": "students:view",
      "name": "View Students",
      "description": "Can view student information"
    },
    {
      "id": 3,
      "code": "students:edit",
      "name": "Edit Students",
      "description": "Can create, update, and delete students"
    }
  ]
}
```

---

## Common Response Structures

### Success Response with Data
```json
{
  "data": { /* Response data */ }
}
```

### Success Response with Pagination
```json
{
  "data": [ /* Array of items */ ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### Error Response
```json
{
  "detail": "Error message here"
}
```

---

## Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required or invalid token
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

---

## Enums Reference

### UserStatus
- `ACTIVE` - User is active
- `INACTIVE` - User is inactive

### StudentStatus
- `ACTIVE` - Student is currently enrolled
- `INACTIVE` - Student is inactive
- `GRADUATED` - Student has graduated
- `EXPELLED` - Student has been expelled

### ContractStatus
- `ACTIVE` - Contract is currently active
- `COMPLETED` - Contract has been completed
- `CANCELLED` - Contract has been cancelled

### PaymentStatus
- `SUCCESS` - Payment completed successfully
- `PENDING` - Payment is pending
- `FAILED` - Payment failed
- `CANCELLED` - Payment was cancelled
- `UNASSIGNED` - Payment not yet assigned to a student

### PaymentSource
- `CASH` - Cash payment
- `CARD` - Card payment
- `BANK_TRANSFER` - Bank transfer
- `ONLINE` - Online payment
- `PAYME` - Payme payment system
- `CLICK` - Click payment system
- `UZUM` - Uzum payment system

### AttendanceStatus
- `PRESENT` - Student was present
- `ABSENT` - Student was absent
- `LATE` - Student arrived late

---

## Permission Codes Reference

### User Management
- `users:manage` - Manage users (create, update, delete, view)

### Student Management
- `students:view` - View student information
- `students:edit` - Create, update, and delete students

### Contract Management
- `contracts:view` - View contracts
- `contracts:edit` - Create, update, and delete contracts

### Finance Management
- `finance:transactions:view` - View all transactions
- `finance:transactions:manual` - Create manual transactions
- `finance:transactions:cancel` - Cancel transactions
- `finance:unassigned:view` - View unassigned transactions
- `finance:unassigned:assign` - Assign unassigned transactions

### Group Management
- `groups:view` - View groups
- `groups:edit` - Create, update, and delete groups

### Attendance Management
- `attendance:coach:mark` - Mark attendance (for coaches)

### Role Management
- `roles:manage` - Manage roles and permissions

---

## Notes

1. **Authentication**: Most endpoints require authentication. Make sure to include the Bearer token in the Authorization header.

2. **Permissions**: Each endpoint has specific permission requirements. Super admins have access to all endpoints automatically.

3. **Pagination**: List endpoints support pagination. Use `page` and `page_size` query parameters to control pagination.

4. **Date Formats**:
   - Dates: `YYYY-MM-DD` (e.g., "2025-12-02")
   - Datetimes: ISO 8601 format with timezone (e.g., "2025-12-02T10:00:00Z")

5. **Contract Validation**: A student can only have one active contract at a time. Attempting to create a second active contract will result in an error.

6. **Face ID Uniqueness**: Face IDs must be unique across all students.

7. **Payment Months**: When creating transactions, payment_months is an array of integers from 1 to 12 representing the months the payment covers.

8. **Attendance Marking**: Coaches can only mark attendance for sessions in groups they are assigned to.
