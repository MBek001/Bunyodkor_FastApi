# Click Payment Integration - Test Guide

## 🚀 Qanday ishlatish

### 1. Talablar
```bash
pip install requests
```

### 2. Konfiguratsiya

`clicktest.py` faylini oching va quyidagilarni o'zgartiring:

```python
# Bu qiymatlarni .env faylingizdan oling
SERVICE_ID = 12345  # CLICK_SERVICE_ID
SECRET_KEY = "your_secret_key_here"  # CLICK_SECRET_KEY

# Databaseda mavjud ACTIVE contract raqamini kiriting
TEST_CONTRACT_NUMBER = "CONTRACT-2024-001"

# Test uchun summa (contract.monthly_fee dan kam bo'lmasligi kerak)
TEST_AMOUNT = 500000.0
```

### 3. Server ishga tushiring

Terminal 1:
```bash
cd /home/user/Bunyodkor_FastApi
uvicorn app.main:app --reload
```

### 4. Testni ishga tushiring

Terminal 2:
```bash
cd /home/user/Bunyodkor_FastApi
python clicktest.py
```

---

## 📊 Testlar

### Test 1: Getinfo (Action 0)
- Contract mavjudligini tekshiradi
- Student ma'lumotlarini qaytaradi
- **Signature talab qilinmaydi**

### Test 2: Prepare (Action 1)
- PENDING transaction yaratadi
- Barcha validatsiyalarni tekshiradi:
  - ✅ Contract ACTIVE mi?
  - ✅ Bugungi sana contract muddatida mi?
  - ✅ Bu oy uchun to'lov mavjud emas-mi?
  - ✅ Summa yetarli mi?
- **Signature talab qilinadi**

### Test 3: Confirm (Action 2)
- Transaction'ni SUCCESS ga o'zgartiradi
- payment_year va payment_months ni to'ldiradi
- **Signature talab qilinadi**

### Test 4: Check (Action 3)
- Transaction statusini tekshiradi
- 0 = PENDING, 1 = FAILED, 2 = SUCCESS
- **Signature talab qilinadi**

---

## ❌ Mumkin bo'lgan xatolar

### Error -1: SIGN CHECK FAILED!
**Sabab**: Imzo noto'g'ri
**Yechim**:
- SECRET_KEY to'g'riligini tekshiring
- paramsIV tartibi to'g'ri ekanligini tekshiring

### Error -2: Incorrect parameter amount
**Sabab**: Amount formati noto'g'ri
**Yechim**: Amount sonli qiymat bo'lishi kerak

### Error -3: Action not found
**Sabab**: service_id noto'g'ri
**Yechim**: SERVICE_ID ni .env dagi CLICK_SERVICE_ID bilan solishtiring

### Error -4: Уже оплачен / Duplikat
**Sabab**: Bu oy uchun to'lov allaqachon mavjud
**Yechim**:
- Boshqa oy uchun sinab ko'ring
- Yoki databasedan o'sha to'lovni o'chiring

### Error -5: Абонент не найден
**Sabab**:
- Contract topilmadi
- Contract ACTIVE emas
- Contract muddati tugagan yoki boshlanmagan

**Yechim**:
- Contract raqamini tekshiring
- Contract statusini tekshiring (ACTIVE bo'lishi kerak)
- Bugungi sana contract.start_date va end_date orasida bo'lishi kerak

### Error -6: Транзакция не найдена
**Sabab**: merchant_prepare_id topilmadi
**Yechim**: Avval PREPARE action'ni muvaffaqiyatli bajaring

### Error -8: Ошибка в запросе от CLICK
**Sabab**: Parametrlar yetarli emas
**Yechim**: Barcha kerakli parametrlarni yuboring

### Error -9: Транзакция отменена
**Sabab**: Transaction CANCELLED statusda
**Yechim**: Yangi transaction yarating

---

## 🔍 Debug

Agar signature xatosi bo'lsa, script quyidagilarni ko'rsatadi:

```
📝 Signature raw string: 123456789987654321123456your_secret_key500000.012025-01-15 10:30:00
🔐 Generated signature: abc123def456...
```

Bu qatorni tekshiring:
- click_paydoc_id: 123456789
- attempt_trans_id: 987654321
- service_id: 12345
- secret_key: your_secret_key
- paramsIV: 500000.0 (params dan keladigan qiymatlar)
- action: 1
- sign_time: 2025-01-15 10:30:00

---

## 📝 Misol natija

Muvaffaqiyatli test:

```
🧪 TEST 1: Action 0 - GETINFO
✅ SUCCESS: Contract found!

🧪 TEST 2: Action 1 - PREPARE
✅ SUCCESS: Transaction prepared!
💾 merchant_prepare_id: 42

🧪 TEST 3: Action 2 - CONFIRM
✅ SUCCESS: Transaction confirmed!
💾 merchant_confirm_id: 42

🧪 TEST 4: Action 3 - CHECK
✅ SUCCESS: Status = 2 (SUCCESS - Click will mark as paid)

📊 TEST SUMMARY
Test 1 (Getinfo):  ✅ PASSED
Test 2 (Prepare):  ✅ PASSED
Test 3 (Confirm):  ✅ PASSED
Test 4 (Check):    ✅ PASSED
```

---

## 🔐 Production uchun

Production'da:
1. `.env` fayldagi CLICK_SERVICE_ID va CLICK_SECRET_KEY ni Click'dan oling
2. Click'ga webhook URL registratsiya qiling: `https://yourdomain.com/click/payment`
3. Click test environment'da sinab ko'ring
4. Keyin production'ga o'ting
