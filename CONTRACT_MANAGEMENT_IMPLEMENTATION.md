# Contract Management System - Implementation Guide

This document outlines the implementation of a comprehensive contract management system with document uploads, digital signatures, and automated contract number allocation.

## Overview

The system manages student enrollment contracts with:
- **Automated contract numbering** based on birth year and group capacity (N{seq}{year})
- **Document management** for all required enrollment documents
- **Digital signature** system with secure signing links
- **Waiting list** management when groups are full
- **PDF generation** and merging of all documents

## ✅ Completed (Phase 1)

### 1. Database Models
- ✅ **Group Model**: Added `capacity` field (default 100 students)
- ✅ **Contract Model**: Extended with:
  - `birth_year` and `sequence_number` for contract numbering
  - Document URL fields: `passport_copy_url`, `form_086_url`, `heart_checkup_url`, `birth_certificate_url`, `contract_images_urls`
  - Digital signature fields: `signature_url`, `signature_token`, `signed_at`
  - `custom_fields` (JSON) for admin-editable handwritten data
  - `group_id` for capacity tracking
  - `final_pdf_url` for merged PDF
- ✅ **WaitingList Model**: New table for students waiting when group is full

### 2. Database Migration
- ✅ Created migration `002_add_contract_management_system.py`
- ✅ Migrates existing contracts with birth year from students
- ✅ Adds all new fields and indexes
- ✅ Creates waiting_list table

### 3. Contract Number Allocation Service
- ✅ `get_available_contract_numbers()`: Returns list of free contract numbers for a group/birth year
- ✅ `allocate_contract_number()`: Auto-assigns next available number
- ✅ `is_group_full()`: Checks if group reached capacity
- ✅ `free_contract_number()`: Releases number when contract terminated
- ✅ Reuses numbers from terminated contracts

### 4. Dependencies
- ✅ Pillow 11.1.0 (image processing)
- ✅ PyPDF2 3.0.1 (PDF merging)
- ✅ reportlab 4.2.5 (PDF generation)

## 🚧 To Be Implemented (Phase 2)

### 5. File Upload System

**Files Needed:**
- `app/services/file_storage.py` - File upload and storage service
- `app/routers/uploads.py` - File upload endpoints

**Features:**
```python
# Upload endpoints needed:
POST /uploads/contract-documents
    - Accept multiple files: passport_copy, form_086, heart_checkup, birth_certificate
    - Accept 5 contract page images
    - Return URLs for each uploaded file
    - Store in: uploads/contracts/{contract_id}/

# Storage structure:
/uploads
  /contracts
    /{contract_id}
      /passport_copy.pdf
      /form_086.pdf
      /heart_checkup.pdf
      /birth_certificate.pdf
      /contract_pages
        /page_1.jpg
        /page_2.jpg
        /page_3.jpg
        /page_4.jpg
        /page_5.jpg
      /signature.png
      /final_contract.pdf
```

**Implementation Steps:**
1. Create `uploads/` directory structure
2. Implement file validation (size, type)
3. Generate unique filenames
4. Save files to disk/S3
5. Return URLs
6. Update contract record with URLs

### 6. Contract Creation with Documents

**Update:** `app/routers/contracts.py`

**New Endpoint:**
```python
POST /contracts/create-with-documents
Request:
{
  "student_id": 123,
  "group_id": 5,
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "monthly_fee": 600000,
  "custom_fields": {
    "parent_name": "Усманов Азизбек Бокиржонович",
    "parent_passport": "АЕ 2220863",
    "parent_address": "Чиланзор 47-уй",
    "payment_months": "10.02 дан 13.04.2025 гача"
  },
  "passport_copy_url": "/uploads/contracts/123/passport.pdf",
  "form_086_url": "/uploads/contracts/123/form_086.pdf",
  "heart_checkup_url": "/uploads/contracts/123/heart.pdf",
  "birth_certificate_url": "/uploads/contracts/123/birth_cert.pdf",
  "contract_images_urls": ["url1", "url2", "url3", "url4", "url5"]
}

Response:
{
  "contract_id": 456,
  "contract_number": "N12020",
  "birth_year": 2020,
  "sequence_number": 1,
  "signature_token": "abc123xyz789",
  "signing_link": "https://app.com/sign/abc123xyz789"
}
```

**Logic:**
1. Check if group is full for student's birth year
2. If full, add to waiting list and return waiting list info
3. If space available, allocate contract number using service
4. Create contract with all document URLs
5. Generate signature token (UUID)
6. Return contract info with signing link

### 7. Digital Signature System

**Files Needed:**
- `app/routers/signatures.py` - Signature endpoints
- `app/services/signature.py` - Signature handling

**Endpoints:**
```python
GET /signatures/verify/{token}
    - Verify token is valid
    - Return contract info for signing page
    - Check if already signed

POST /signatures/sign/{token}
Request:
{
  "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANS..."
}
Response:
{
  "success": true,
  "message": "Contract signed successfully",
  "signed_at": "2025-12-04T10:30:00Z"
}
```

**Implementation:**
1. Generate unique secure token (UUID4)
2. Store token in contract.signature_token
3. Create signing page (frontend or simple HTML)
4. Accept base64 signature image
5. Save signature as PNG file
6. Update contract: signature_url, signed_at
7. Invalidate token after signing
8. Trigger PDF generation

### 8. PDF Generation and Merging

**File Needed:**
- `app/services/pdf_generator.py`

**Features:**
```python
async def generate_final_pdf(contract_id: int) -> str:
    """
    Merge all contract documents into single PDF:
    1. 5 contract page images → PDF
    2. Passport copy
    3. Form 086
    4. Heart checkup
    5. Birth certificate
    6. Signature page

    Returns: URL to final merged PDF
    """
```

**Implementation Steps:**
1. Load all document URLs from contract
2. Convert images to PDF pages (using Pillow + reportlab)
3. Merge all PDFs using PyPDF2
4. Add signature image to signature page
5. Save as `final_contract_{contract_number}.pdf`
6. Update contract.final_pdf_url
7. Return download URL

**Endpoint:**
```python
POST /contracts/{contract_id}/generate-pdf
    - Generate final merged PDF
    - Return download URL

GET /contracts/{contract_id}/download-pdf
    - Download the final PDF
```

### 9. Waiting List Management

**File:** `app/routers/waiting_list.py`

**Endpoints:**
```python
POST /waiting-list/add
Request:
{
  "student_id": 123,
  "group_id": 5,
  "priority": 1,
  "notes": "Urgent enrollment needed"
}

GET /waiting-list/group/{group_id}
    - Get all students waiting for this group
    - Ordered by priority (high to low), then created_at

POST /waiting-list/{waiting_id}/assign-contract
    - When slot becomes available
    - Move student from waiting list to group
    - Create contract with freed number
    - Remove from waiting list

DELETE /waiting-list/{waiting_id}
    - Remove student from waiting list
```

### 10. Available Contract Numbers API

**Update:** `app/routers/contracts.py`

**New Endpoints:**
```python
GET /contracts/available-numbers/{group_id}/{birth_year}
Response:
{
  "group_id": 5,
  "group_name": "U17",
  "group_capacity": 100,
  "birth_year": 2020,
  "available_numbers": [1, 5, 12, 23, 45],  # N12020, N52020, etc.
  "total_available": 5,
  "total_used": 95,
  "is_full": false
}

GET /contracts/next-available/{group_id}/{birth_year}
Response:
{
  "next_available": 1,
  "contract_number": "N12020"
}
```

### 11. Contract Cancellation with Number Release

**Update:** `app/routers/contracts.py`

**Enhance Existing Terminate Endpoint:**
```python
POST /contracts/{contract_id}/terminate
    - Mark contract as TERMINATED
    - Free the contract number
    - Check waiting list for this group
    - Suggest student from waiting list
    - Return available number for reassignment

Response:
{
  "message": "Contract terminated",
  "freed_number": "N12020",
  "freed_sequence": 1,
  "birth_year": 2020,
  "waiting_list_count": 3,
  "next_waiting_student": {
    "student_id": 456,
    "student_name": "Ali Valiyev",
    "priority": 1
  }
}
```

### 12. Group Capacity Management

**Update:** `app/routers/groups.py`

**Enhance Group Endpoints:**
```python
GET /groups/{group_id}/capacity
Response:
{
  "group_id": 5,
  "group_name": "U17",
  "capacity": 100,
  "active_contracts": 95,
  "available_slots": 5,
  "waiting_list_count": 3,
  "by_birth_year": {
    "2020": {"used": 30, "available": 70},
    "2019": {"used": 40, "available": 60},
    "2018": {"used": 25, "available": 75}
  }
}

PATCH /groups/{group_id}/capacity
Request:
{
  "capacity": 150
}
    - Update group capacity
    - Recalculate available slots
```

## 📋 Implementation Checklist

### Phase 2A - File Management
- [ ] Create file storage service
- [ ] Add file upload endpoints
- [ ] Implement file validation
- [ ] Test file uploads

### Phase 2B - Contract Creation
- [ ] Update contract creation endpoint
- [ ] Integrate contract number allocation
- [ ] Add group full check
- [ ] Add waiting list integration
- [ ] Generate signature tokens
- [ ] Test contract creation flow

### Phase 2C - Digital Signatures
- [ ] Create signature endpoints
- [ ] Implement signature verification
- [ ] Save signature images
- [ ] Create simple signing page (HTML)
- [ ] Test signing flow

### Phase 2D - PDF Generation
- [ ] Create PDF merging service
- [ ] Convert images to PDF
- [ ] Merge all documents
- [ ] Add signature to final PDF
- [ ] Create download endpoint
- [ ] Test PDF generation

### Phase 2E - Waiting List
- [ ] Create waiting list endpoints
- [ ] Implement priority queue
- [ ] Add assign-to-contract endpoint
- [ ] Integrate with contract creation
- [ ] Test waiting list flow

### Phase 2F - Admin Tools
- [ ] Available numbers API
- [ ] Group capacity API
- [ ] Contract reassignment tools
- [ ] Bulk operations
- [ ] Analytics dashboard

## 🔧 Database Migration

**Run Migration:**
```bash
# Install new dependencies first
pip install -r requirements.txt

# Run migration
alembic upgrade head
```

## 📁 Directory Structure

```
/uploads
  /contracts
    /{contract_id}
      /passport_copy.{ext}
      /form_086.{ext}
      /heart_checkup.{ext}
      /birth_certificate.{ext}
      /contract_pages
        /page_{1-5}.{ext}
      /signature.png
      /final_contract.pdf
```

## 🔐 Security Considerations

1. **File Uploads:**
   - Validate file types (PDF, JPG, PNG only)
   - Limit file sizes (max 10MB per file)
   - Scan for malware
   - Use secure filenames (no user input in names)

2. **Signature Tokens:**
   - Use UUID4 for unpredictability
   - Expire tokens after 24 hours or after signing
   - One-time use only
   - Store securely

3. **Access Control:**
   - Only super admin can manage waiting list
   - Only admin and above can create contracts
   - Students/parents can only sign their own contracts
   - Validate permissions on all endpoints

## 🎯 Next Steps

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run migration:**
   ```bash
   alembic upgrade head
   ```

3. **Implement Phase 2A** (File uploads) first
4. Then proceed sequentially through phases

## 📞 Support

For implementation questions or issues, please create a GitHub issue with:
- Phase and step number
- Error message or question
- Relevant code snippet

---

**Note:** This is a large feature requiring significant development time. Estimated implementation time: 20-30 hours for complete system.
