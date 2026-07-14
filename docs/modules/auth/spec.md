# Auth Module - Functional Specification

**Module:** Xac thuc nguoi dung  
**Route prefix:** `/api/v1/auth`  
**Files:** `routes/auth.py`, `controllers/auth_controller.py`, `services/auth_service.py`

---

## 1. User Flows

### 1.1 Flow Dang ky -> OTP Verify -> Dang nhap

```
[1] User truy cap /signin
    │
    ▼
[2] Nhap username, email, password
    │ POST /auth/register
    │
    ▼
[3] He thong:
    ├── Kiem tra username da ton tai?
    │   ├── Da verify -> Bao loi "Tai khoan da duoc dang ky"
    │   └── Chua verify -> Cap nhat password moi
    ├── Kiem tra email da su dung boi tai khoan khac?
    │   └── Da su dung -> Bao loi "Email da duoc su dung"
    ├── Tao user moi (role='user', is_verified=0, is_active=True)
    ├── Hash password (PBKDF2)
    ├── Tao OTP 6 so
    ├── Luu token vao DB (type='email_verify', expires_in=5min)
    ├── Gui OTP qua Gmail (hoac in ra console neu SMTP chua cau hinh)
    └── Ghi nhat ky hoat dong
    │
    ▼
[4] Nhap ma OTP
    │ POST /auth/verify-otp
    │
    ▼
[5] He thong:
    ├── Tim user theo username
    ├── Kiem tra tai khoan da verify?
    │   └── Da verify -> Tra ve "Da duoc xac thuc truoc do"
    ├── Tim token hop le (user_id + token + type='email_verify' + is_used=False)
    ├── Kiem tra OTP het han? (> 5 phut -> bao loi)
    ├── Cap nhat is_verified=1, is_active=True
    ├── Danh dau token is_used=True
    └── Tra ve "Kich hoat tai khoan thanh cong"
    │
    ▼
[6] Dang nhap
    │ POST /auth/login
    │
    ▼
[7] He thong:
    ├── Tim user theo username
    ├── Kiem tra tai khoan ton tai?
    ├── Kiem tra is_verified == 1?
    │   └── Chua verify -> Bao loi "Chua kich hoat bang OTP"
    ├── Kiem tra is_active == True?
    │   └── Bi vo hieu hoa -> Bao loi
    ├── Xac thuc password (PBKDF2)
    │   └── Sai -> Ghi log that bai, bao loi
    ├── Cap nhat last_login_at
    ├── Ghi nhat ky dang nhap (neu dung dieu kien)
    └── Tra ve user info {id, username, email, role, is_verified, is_active}
```

### 1.2 Flow Quen mat khau -> OTP -> Dat lai mat khau

```
[1] User quen mat khau
    │ POST /auth/forgot-password
    │ { username }
    │
    ▼
[2] He thong:
    ├── Tim user theo username
    ├── Kiem tra tai khoan ton tai?
    ├── Tao OTP 6 so moi
    ├── Xoa OTP cu cung type='password_reset'
    ├── Luu token moi (type='password_reset', expires_in=5min)
    ├── Gui OTP qua Gmail
    └── Tra ve message
    │
    ▼
[3] Nhap OTP va mat khau moi
    │ POST /auth/reset-password
    │ { username, otp, new_password }
    │
    ▼
[4] He thong:
    ├── Tim user theo username
    ├── Tim token hop le (user_id + token + type='password_reset' + is_used=False)
    ├── Kiem tra OTP het han?
    ├── Kiem tra mat khau moi KHONG duoc trung mat khau cu
    ├── Hash mat khau moi (PBKDF2)
    ├── Cap nhat password_hash
    ├── Danh dau token is_used=True
    ├── Cap nhat is_verified=1 (tu dong xac thuc)
    └── Tra ve "Dat lai mat khau thanh cong"
```

### 1.3 Flow Dang xuat

```
[1] User dang xuat
    │ POST /auth/logout
    │ { username }
    │
    ▼
[2] He thong:
    ├── Tim user theo username
    ├── Cap nhat last_logout_at
    └── Ghi nhat ky dang xuat
```

---

## 2. API Endpoints Chi Tiet

### 2.1 POST `/auth/register`

**Muc dich:** Dang ky tai khoan moi, gui OTP xac thuc.

**Request Body:**
```json
{
  "username": "string (bat buoc)",
  "email": "string (bat buoc)",
  "password": "string (bat buoc)"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Ma OTP xac thuc da duoc gui ve Gmail cua ban.",
  "username": "nguoidung",
  "email": "user@gmail.com",
  "dev_mode": false
}
```

**Response (400):**
```json
{
  "detail": "Tai khoan nay da duoc dang ky."
}
```

**Response (400):**
```json
{
  "detail": "Email nay da duoc su dung boi tai khoan khac."
}
```

**Ghi chu:**
- Neu tai khoan da ton tai chua verify -> cap nhat password moi
- Neu SMTP chua cau hinh -> dev_mode=true, OTP in console

### 2.2 POST `/auth/verify-otp`

**Muc dich:** Xac thuc OTP de kich hoat tai khoan.

**Request Body:**
```json
{
  "username": "string (bat buoc)",
  "otp": "string (6 ky tu so)"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Kich hoat tai khoan thanh cong! Ban co the dang nhap."
}
```

**Response (400):**
```json
{
  "detail": "Ma OTP khong chinh xac."
}
```

**Response (400):**
```json
{
  "detail": "Ma OTP da het han. Vui long gui lai ma moi."
}
```

### 2.3 POST `/auth/resend-otp`

**Muc dich:** Gui lai ma OTP xac thuc.

**Request Body:**
```json
{
  "username": "string (bat buoc)"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Ma OTP moi da duoc gui ve Gmail cua ban.",
  "username": "nguoidung",
  "email": "user@gmail.com",
  "dev_mode": false
}
```

### 2.4 POST `/auth/login`

**Muc dich:** Dang nhap vao he thong.

**Request Body:**
```json
{
  "username": "string (bat buoc)",
  "password": "string (bat buoc)"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Dang nhap thanh cong.",
  "user": {
    "id": 1,
    "username": "nguoidung",
    "email": "user@gmail.com",
    "role": "user",
    "is_verified": 1,
    "is_active": true
  }
}
```

**Response (400):**
```json
{
  "detail": "Tai khoan hoac mat khau khong chinh xac."
}
```

**Response (400):**
```json
{
  "detail": "Tai khoan chua duoc kich hoat bang OTP. Vui long xac thuc truoc."
}
```

**Response (400):**
```json
{
  "detail": "Tai khoan da bi vo hieu hoa."
}
```

### 2.5 POST `/auth/forgot-password`

**Muc dich:** Gui OTP khôi phục mat khau.

**Request Body:**
```json
{
  "username": "string (bat buoc)"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Ma OTP dat lai mat khau da duoc gui ve Gmail cua tai khoan nay.",
  "username": "nguoidung",
  "email": "user@gmail.com",
  "dev_mode": false
}
```

### 2.6 POST `/auth/reset-password`

**Muc dich:** Dat lai mat khau moi bang OTP.

**Request Body:**
```json
{
  "username": "string (bat buoc)",
  "otp": "string (6 ky tu so)",
  "new_password": "string (bat buoc)"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Dat lai mat khau moi thanh cong! Ban da co the dang nhap."
}
```

**Response (400):**
```json
{
  "detail": "Mat khau moi khong duoc trung mat khau cu."
}
```

### 2.7 POST `/auth/logout`

**Muc dich:** Dang xuat, cap nhat thoi gian dang xuat.

**Request Body:**
```json
{
  "username": "string (bat buoc)"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Dang xuat thanh cong."
}
```

### 2.8 GET `/auth/test-email`

**Muc dich:** Test ket noi SMTP Gmail.

**Query Params:**
- `email`: Dia chi email can test (default: `test@gmail.com`)

**Response (200):**
```json
{
  "status": "success",
  "message": "Gui email test thanh cong den test@gmail.com!",
  "smtp_user": "vietc3k49@gmail.com",
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587
}
```

---

## 3. Business Rules

### 3.1 Password Hashing

- Thuat toan: PBKDF2-HMAC-SHA256
- So lan lap: 100,000
- Salt: 16 bytes ngau nhien (os.urandom)
- Dinh dang hash: `salt_hex:key_hex`
- VD: `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6:9f8e7d6c5b4a3...`

### 3.2 JWT Token Flow

Hien tai he thong su dung session-based auth thoi qua HTTP cookies/response body, JWT chua duoc su dung truc tiep trong login flow. PyJWT da duoc cai dat (v2.10.1) cho muc dich keo dai.

### 3.3 OTP Generation

- Ma OTP: 6 ky tu so, dinh dang `{:06d}` (VD: `000001`, `123456`)
- Ngau nhien: `random.randint(0, 999999)`
- Thoi han: 5 phut tu thoi diem tao
- Moi tai khoan chi co 1 OTP hop le (OTP cu bi xoa khi tao moi)
- 2 loai: `email_verify` (dang ky) va `password_reset` (quen mat khau)

### 3.4 Login Logging Logic

Chi ghi nhat ky dang nhap khi:
- `last_login_at` la NULL (lan dau dang nhap), HOAC
- `last_logout_at > last_login_at` (da dang xuat truoc do)

Muc dich: tranh ghi log moi lan user reload trang.

---

## 4. Error Handling Scenarios

| Tinh huong | HTTP Code | Message |
|---|---|---|
| Username trong | 400 | "Tai khoan khong duoc bo trong." |
| Email trong | 400 | "Email khong duoc bo trong." |
| Username da verify | 400 | "Tai khoan nay da duoc dang ky." |
| Email da duoc su dung | 400 | "Email nay da duoc su dung boi tai khoan khac." |
| Username khong ton tai | 404 | "Khong tim thay thong tin tai khoan." |
| OTP sai | 400 | "Ma OTP khong chinh xac." |
| OTP het han | 400 | "Ma OTP da het han. Vui long gui lai ma moi." |
| Tai khoan chua verify | 400 | "Tai khoan chua duoc kich hoat bang OTP." |
| Tai khoan bi vo hieu hoa | 400 | "Tai khoan da bi vo hieu hoa." |
| Sai mat khau | 400 | "Tai khoan hoac mat khau khong chinh xac." |
| Mat khau moi trung cu | 400 | "Mat khau moi khong duoc trung mat khau cu." |
| Username khong ton tai (forgot) | 404 | "Tai khoan khong ton tai." |
| Tai khoan da verify (resend) | 400 | "Tai khoan nay da duoc xac thuc." |
| SMTP chua cau hinh | 200 | Tra ve dev_mode=true, OTP in console |

---

## 5. Development Mode

Khi SMTP chua duoc cau hinh (SMTP_USER hoac SMTP_PASSWORD la None):
- OTP duoc in ra console: `[DEVELOPMENT MODE] OTP code for {username} ({email}) is: {otp}`
- Response include `dev_mode: true` de frontend biet
- Toan luong dang ky -> OTP verify -> dang nhap van hoat dong binh thuong
- Khong can SMTP de phat trien va test
