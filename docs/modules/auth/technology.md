# Auth Module - Technology Specification

**Module:** Xac thuc nguoi dung  
**Files:** `services/auth_service.py`, `utils/security.py`, `utils/email.py`

---

## 1. JWT Configuration

### 1.1 Hien trang

He thong hien tai su dung **session-based authentication** thoi qua HTTP request/response body. JWT da duoc cai dat (`PyJWT 2.10.1`) nhung chua duoc su dung truc tiep trong login flow.

### 1.2 Cau hinh (keo dai)

| Tham so | Gia tri | Mo ta |
|---|---|---|
| **Algorithm** | HS256 | HMAC-SHA256 |
| **Secret Key** | Tu env variable | JWT_SECRET_KEY |
| **Access Token Expiry** | 24 gio | Token het han sau 24h |
| **Refresh Token Expiry** | 7 ngay | Token lam moi sau 7 ngay |

### 1.3 Flow (keo dai)

```
[1] Login -> Tao access_token + refresh_token
[2] Client luu token (localStorage/cookie)
[3] Moi request -> Authorization: Bearer <access_token>
[4] Backend verify token -> Extract user_id, role
[5] Access token het han -> Dung refresh_token de lay moi
[6] Refresh token het han -> Dang nhap lai
```

---

## 2. PBKDF2 Password Hashing

### 2.1 Implementation

Thu vien: `hashlib` (Python standard library)  
Thuat toan: `PBKDF2-HMAC-SHA256`

### 2.2 Configuration

| Tham so | Gia tri | Mo ta |
|---|---|---|
| **Algorithm** | SHA-256 | Hash function |
| **Iterations** | 100,000 | So lap PBKDF2 |
| **Salt Length** | 16 bytes | Salt ngau nhien |
| **Key Length** | 32 bytes (256 bit) | Do dai key output |

### 2.3 Hash Format

```
salt_hex:key_hex

VD: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6:9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e
```

### 2.4 Code

```python
import os
import hashlib

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + key.hex()

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception:
        return False
```

### 2.5 Security Notes

- `os.urandom(16)` tao salt ngau nen tren CSPRNG cua OS
- 100,000 iterations la muc khuyen nghi OWASP (2023+)
- Khong can luu salt rieng vi salt da nam trong hash string
- `verify_password` tra ve False neu hash format sai (exception handling)

---

## 3. SMTP Gmail Setup for OTP

### 3.1 Configuration

| Tham so | Gia tri | Mo ta |
|---|---|---|
| **SMTP Server** | smtp.gmail.com | Gmail SMTP server |
| **SMTP Port** | 587 | TLS port |
| **Security** | STARTTLS | Upgrade to TLS |
| **Timeout** | 15 giay | Ket noi timeout |
| **From Name** | Vietnamese license plates AI | Ten hien thi |
| **From Email** | SMTP_USER | Dia chi gui |

### 3.2 Environment Variables

```env
SMTP_USER=vietc3k49@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### 3.3 Gmail App Password Setup

1. Dang nhap tai khoan Gmail tren trinh duyet
2. Vao App Passwords: https://myaccount.google.com/apppasswords
3. Chon "Create app password"
   - App name: `Vietnam LPR` (tuy y)
   - Nhan "Create"
4. Copy mat khung ung dung (16 ky tu, VD: `abcd efgh ijkl mnop`)
5. Paste vao `SMTP_PASSWORD` trong file `.env`

### 3.4 Email Content (OTP)

```html
<div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
  <h2 style="color: #4f46e5;">Xac nhan thao tac tren Vietnam LPR</h2>
  <p>Chao ban,</p>
  <p>Ma OTP xac thuc cua ban la:</p>
  <div style="text-align: center; margin: 30px 0;">
    <span style="font-size: 32px; font-weight: bold; color: #4f46e5; letter-spacing: 5px;">
      {otp}
    </span>
  </div>
  <p>Ma OTP nay co hieu luc trong vong <b>5 phut</b>.</p>
</div>
```

### 3.5 SMTP Connection Flow

```
[1] Tao MIMEMultipart message
    ├── From: "Vietnamese license plates AI <SMTP_USER>"
    ├── To: to_email
    ├── Subject: "Ma OTP xac thuc Vietnam LPR"
    └── Body: HTML voi OTP

[2] Ket noi SMTP
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
    server.ehlo()
    server.starttls()           # Upgrade to TLS
    server.ehlo()
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.sendmail(SMTP_USER, to_email, msg.as_string())

[3] Cleanup
    server.quit()
```

### 3.6 Error Handling

| Loai loi | Xu ly |
|---|---|
| **SMTPAuthenticationError** | Sai tai khoan hoac App Password |
| **SMTPConnectError** | Khong the ket noi SMTP server |
| **TimeoutError** | Timeout ket noi (15s) |
| **Exception chung** | Loai ngoai khong xac dinh |

Tat ca cac loi deu tra ve `False` va in log chi tiet.

### 3.7 Development Mode

Khi SMTP chua cau hinh (SMTP_USER hoac SMTP_PASSWORD la None):
- Khong gui email
- OTP in ra console: `[EMAIL] OTP cho {email} la: {otp}`
- Ham `send_otp_email()` tra ve `False`
- Ham `test_smtp_connection()` tra ve `{ ok: False, message: "SMTP chua cau hinh" }`

---

## 4. PyJWT Library Details

### 4.1 Installation

```
PyJWT==2.10.1
```

### 4.2 Usage (keo dai)

```python
import jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(hours=24)

def create_access_token(user_id: int, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + ACCESS_TOKEN_EXPIRE
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token het han.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token khong hop le.")
```

---

## 5. Dependency Injection (FastAPI)

### 5.1 Database Session

```python
from sqlalchemy.orm import Session
from src.config.database import get_db

@router.post("/login")
async def login(
    credentials: schemas.UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    return await AuthController.login(credentials, request, db)
```

### 5.2 Background Tasks

```python
from fastapi import BackgroundTasks

@router.post("/register")
async def register(
    user_data: schemas.UserRegister,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    return await AuthController.register(user_data, request, background_tasks, db)
```

### 5.3 Request Client Info

```python
from fastapi import Request

client_ip = request.client.host if request.client else ""
```

---

## 6. Session Management

### 6.1 Current Implementation

Hien tai he thong khong su dung JWT cookies. Thay vao do:
- Login tra ve user info trong response body
- Frontend luu user info trong React state / localStorage
- Moi request gui user_id hoac token qua header/query params

### 6.2 Login/Logout Tracking

```python
# Login
user.last_login_at = get_vietnam_now().replace(tzinfo=None)

# Logout
user.last_logout_at = get_vietnam_now().replace(tzinfo=None)

# Dieu kien ghi log dang nhap:
should_log = (
    user.last_login_at is None
    or (
        user.last_logout_at is not None
        and user.last_login_at is not None
        and user.last_logout_at > user.last_login_at
    )
)
```
