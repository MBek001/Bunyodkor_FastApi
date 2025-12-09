# 🗄️ Archive System Setup Guide

## Xatolarni Hal Qilish

Agar quyidagi xatolar paydo bo'lsa:

### 1. `StudentStatus is not defined`
**Hal qilindi!** ✅ - `students.py` ga import qo'shildi

### 2. `'active' is not among the defined enum values`
**Sabab:** Ma'lumotlar bazasida migration ishga tushmagan

**Yechim:** Quyidagi qadamlarni bajaring:

---

## 🚀 Migration'larni Ishga Tushirish

### Variant 1: Alembic orqali (Tavsiya etiladi)

```bash
# Terminal'da loyiha papkasida
cd /home/user/Bunyodkor_FastApi

# Virtual environment'ni faollashtiring (agar bor bo'lsa)
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Migration'larni ishga tushirish
alembic upgrade head
```

### Variant 2: Python orqali

```bash
python -m alembic upgrade head
```

### Variant 3: Manual SQL (Agar Alembic ishlamasa)

PostgreSQL'ga ulanib, quyidagi faylni ishga tushiring:

```bash
psql -U your_username -d bunyodkor_db -f migrations_manual.sql
```

Yoki pgAdmin/DBeaver'da `migrations_manual.sql` faylini oching va Run qiling.

---

## ✅ Migration Muvaffaqiyatli Bajarilganini Tekshirish

PostgreSQL'da quyidagi query'ni ishga tushiring:

```sql
-- Barcha ustunlar mavjudligini tekshirish
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('groups', 'students', 'contracts')
    AND column_name IN ('archive_year', 'status')
ORDER BY table_name, column_name;
```

**Kutilgan natija:**
- `groups.archive_year` - integer
- `groups.status` - varchar(20)
- `students.archive_year` - integer
- `contracts.archive_year` - integer

---

## 🎯 Tizimni Test Qilish

### 1. Serverini Ishga Tushirish

```bash
python main.py
# yoki
uvicorn main:app --reload
```

### 2. Swagger UI'da Test

```
http://localhost:8000/docs
```

### 3. Guruhlarni Olish (Bo'sh List)

```bash
GET /groups
# Natija: Bo'sh [] (chunki hamma default 2025 yil, status=active)
```

### 4. Yangi Guruh Yaratish

```bash
POST /groups
{
  "name": "U-10 Guruh",
  "capacity": 100,
  "coach_id": 1
}
# Avtomatik: archive_year=2025, status=active
```

### 5. Arxivlash (Superuser)

```bash
POST /archive/year/2025
Authorization: Bearer {superuser_token}

# Natija: Barcha 2025 data -> status=archived
```

### 6. Arxivlangan Ma'lumotlarni Ko'rish

```bash
GET /groups?include_archived=true
GET /students?include_archived=true
```

---

## 📝 API Endpoints

### Archive Endpoints (Superuser Only)

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| POST | `/archive/year/{year}` | Yilni arxivlash |
| POST | `/archive/unarchive/year/{year}` | Arxivni bekor qilish |
| GET | `/archive/stats/{year}` | Statistika |

### List Endpoints (Updated)

| Method | Endpoint | Yangi Parametr |
|--------|----------|----------------|
| GET | `/groups` | `?include_archived=false` |
| GET | `/students` | `?include_archived=false` |

---

## ❗ Muhim Eslatmalar

1. **Migration'larni ishga tushirish majburiy!**
   - Aks holda xatolar paydo bo'ladi

2. **Superuser kerak:**
   - Archive endpointlar faqat superuser uchun

3. **Backup oling:**
   - Arxivlashdan oldin har doim backup oling

4. **Test muhitida sinab ko'ring:**
   - Production'da ishlatishdan oldin test qiling

---

## 🆘 Yordam

Agar xatolar davom etsa:

1. Ma'lumotlar bazasi ulanishini tekshiring
2. Migration fayllarni tekshiring: `alembic/versions/`
3. Logs'ni tekshiring: `uvicorn` output
4. PostgreSQL user'ining ruxsatlarini tekshiring

---

## 📚 Qo'shimcha Ma'lumot

- Barcha o'zgarishlar commit qilindi ✅
- Migration fayllar yaratildi ✅
- Documentation tayyorlandi ✅

**Keyingi qadam:** Migration'larni ishga tushiring!
