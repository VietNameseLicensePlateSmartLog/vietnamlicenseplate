# Auth Module - Data Specification

**Module:** Xac thuc nguoi dung  
**Tables:** users, tokens

---

## 1. User Table Schema

```sql
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    email           VARCHAR(100) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100),
    role            VARCHAR(20) NOT NULL DEFAULT 'user',
    is_verified     SMALLINT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    last_login_at   TIMESTAMP,
    last_logout_at  TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

### 1.1 Field Definitions

| Field | Kieu du lieu | Mo ta | Rang buoc |
|---|---|---|---|
| `id` | INTEGER (PK) | ID tu tang | BAT BUOC, auto |
| `username` | VARCHAR(50) | Ten tai khoan | BAT BUOC, UNIQUE, INDEX |
| `email` | VARCHAR(100) | Dia chi email | BAT BUOC, UNIQUE, INDEX |
| `password_hash` | VARCHAR(255) | Mat khau da hash (PBKDF2) | BAT BUOC |
| `full_name` | VARCHAR(100) | Ho ten day du | Tu chon |
| `role` | VARCHAR(20) | Vai tro: 'user' hoac 'admin' | BAT BUOC, mac dinh 'user' |
| `is_verified` | SMALLINT | Trang thai xac thuc: 0=chua, 1=da verify | BAT BUOC, mac dinh 0 |
| `is_active` | BOOLEAN | Trang thai kich hoat | BAT BUOC, mac dinh TRUE |
| `failed_attempts` | INTEGER | So lan dang nhap that bai | BAT BUOC, mac dinh 0 |
| `last_login_at` | TIMESTAMP | Lan dang nhap cuoi cung | Tu chon |
| `last_logout_at` | TIMESTAMP | Lan dang xuat cuoi cung | Tu chon |
| `created_at` | TIMESTAMP | Thoi gian tao | Auto |
| `updated_at` | TIMESTAMP | Thoi gian cap nhat | Auto (onupdate) |

### 1.2 Indexes

- `ix_users_id` (PRIMARY KEY)
- `ix_users_username` (UNIQUE, on username)
- `ix_users_email` (UNIQUE, on email)

### 1.3 Sample Data

```sql
-- Admin mac dinh
INSERT INTO users (username, email, password_hash, full_name, role, is_verified, is_active)
VALUES ('abc1', 'admin@lpr.vn', '<hash>', 'Admin', 'admin', 1, TRUE);

-- User da verify
INSERT INTO users (username, email, password_hash, role, is_verified, is_active)
VALUES ('nguoidung', 'user@gmail.com', '<hash>', 'user', 1, TRUE);

-- User chua verify
INSERT INTO users (username, email, password_hash, role, is_verified, is_active)
VALUES ('testuser', 'test@gmail.com', '<hash>', 'user', 0, TRUE);
```

---

## 2. Token Table Schema

```sql
CREATE TABLE tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(255) NOT NULL UNIQUE,
    type        VARCHAR(20) NOT NULL,
    expires_at  TIMESTAMP NOT NULL,
    is_used     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 2.1 Field Definitions

| Field | Kieu du lieu | Mo ta | Rang buoc |
|---|---|---|---|
| `id` | INTEGER (PK) | ID tu tang | BAT BUOC, auto |
| `user_id` | INTEGER (FK -> users.id) | ID nguoi dung so huu token | BAT BUOC, CASCADE DELETE |
| `token` | VARCHAR(255) | Ma OTP (6 ky tu so) | BAT BUOC, UNIQUE, INDEX |
| `type` | VARCHAR(20) | Loai token: 'email_verify' hoac 'password_reset' | BAT BUOC |
| `expires_at` | TIMESTAMP | Thoi het han | BAT BUOC |
| `is_used` | BOOLEAN | Da su dung chua | BAT BUOC, mac dinh FALSE |
| `created_at` | TIMESTAMP | Thoi gian tao | Auto |

### 2.2 Token Types

| Gia tri | Mo ta | Su dung khi |
|---|---|---|
| `email_verify` | Token xac thuc email | Dang ky tai khoan moi |
| `password_reset` | Token dat lai mat khau | Quen mat khau |

### 2.3 Token Lifecycle

```
[1] Tao token moi:
    - Xoa tat ca token cu cung user_id + type
    - Tao token moi voi expires_at = now + 5 phut
    - is_used = FALSE

[2] Su dung token:
    - Tim token: user_id + token + type + is_used=FALSE
    - Kiem tra expires_at > now
    - Cap nhat is_used = TRUE
```

---

## 3. Request/Response Schemas

### 3.1 UserRegister

```python
class UserRegister(BaseModel):
    username: str    # Bat buoc
    email: str       # Bat buoc
    password: str    # Bat buoc
```

### 3.2 UserVerifyOTP

```python
class UserVerifyOTP(BaseModel):
    username: str    # Bat buoc
    otp: str         # 6 ky tu so
```

### 3.3 UserLogin

```python
class UserLogin(BaseModel):
    username: str    # Bat buoc
    password: str    # Bat buoc
```

### 3.4 ForgotPasswordRequest

```python
class ForgotPasswordRequest(BaseModel):
    username: str    # Bat buoc
```

### 3.5 ResetPasswordRequest

```python
class ResetPasswordRequest(BaseModel):
    username: str        # Bat buoc
    otp: str             # 6 ky tu so
    new_password: str    # Bat buoc, khong duoc trung cu
```

### 3.6 UserResponse

```python
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_verified: int
    is_active: bool

    class Config:
        from_attributes = True
```

### 3.7 Register Response

```json
{
  "status": "success",
  "message": "Ma OTP xac thuc da duoc gui ve Gmail cua ban.",
  "username": "nguoidung",
  "email": "user@gmail.com",
  "dev_mode": false
}
```

### 3.8 Login Response

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

---

## 4. Data Flow: Register -> Token -> OTP -> Verify -> Activated

```
[1] POST /auth/register
    │
    ├──> Kiem tra User.username ton tai?
    │    ├── YES (da verify) -> 400 "Da dang ky"
    │    ├── YES (chua verify) -> Cap nhat password
    │    └── NO -> Tao User moi
    │
    ├──> Kiem tra User.email da su dung?
    │    └── YES (is_verified=1) -> 400 "Email da su dung"
    │
    ├──> Hash password (PBKDF2)
    ├──> Luu User vao DB
    │
    ├──> Xoa Token cu (user_id=X, type='email_verify')
    ├──> Tao Token moi:
    │    user_id = X
    │    token = "123456" (6 so)
    │    type = "email_verify"
    │    expires_at = now + 5 phut
    │    is_used = FALSE
    ├──> Gui OTP qua Gmail (hoac in console)
    │
    └──> Response: { status, message, username, email, dev_mode }

[2] POST /auth/verify-otp
    │
    ├──> Tim User theo username
    │    └── Khong tim thay -> 404
    │
    ├──> Kiem tra User.is_verified == 1?
    │    └── YES -> Tra ve "Da xac thuc truoc do"
    │
    ├──> Tim Token:
    │    user_id = X
    │    token = input_otp
    │    type = "email_verify"
    │    is_used = FALSE
    │    └── Khong tim thay -> 400 "OTP sai"
    │
    ├──> Kiem tra Token.expires_at > now?
    │    └── Het han -> 400 "OTP het han"
    │
    ├──> User.is_verified = 1
    ├──> User.is_active = TRUE
    ├──> Token.is_used = TRUE
    ├──> DB commit
    │
    └──> Response: { status, message }

[3] POST /auth/login
    │
    ├──> Tim User theo username
    │    └── Khong tim thay -> 400 "Sai mat khau"
    │
    ├──> Kiem tra User.is_verified == 1?
    │    └── NO -> 400 "Chua kich hoat OTP"
    │
    ├──> Kiem tra User.is_active == TRUE?
    │    └── NO -> 400 "Da bi vo hieu hoa"
    │
    ├──> Xac thuc password (PBKDF2 verify)
    │    └── Sai -> Ghi log that bai -> 400 "Sai mat khau"
    │
    ├──> User.last_login_at = now
    ├──> Ghi log dang nhap (neu dung dieu kien)
    │
    └──> Response: { status, message, user: { id, username, email, role, ... } }
```
