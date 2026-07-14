import random
import string
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.modules.auth.models import User, Token
from src.modules.auth.schemas import UserRegister, UserLogin
from src.core.utils.security import hash_password, verify_password
from src.core.utils.email import send_otp_email
from src.core.utils.helpers import log_activity, get_vietnam_now

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

class AuthService:
    @staticmethod
    def register(payload: UserRegister, db: Session, request=None):
        if db.query(User).filter(User.username == payload.username).first():
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại.")
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Email đã được sử dụng.")
        user = User(
            username=payload.username,
            email=payload.email,
            full_name=payload.username,
            password_hash=hash_password(payload.password),
            is_verified=0,
            is_active=True,
            failed_attempts=0
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        otp_code = generate_otp()
        otp_token = Token(
            user_id=user.id,
            token=otp_code,
            type="email_verify",
            expires_at=get_vietnam_now() + timedelta(minutes=5)
        )
        db.add(otp_token)
        db.commit()
        ip_address = ""
        if request:
            ip_address = request.client.host if request.client else ""
        log_activity(db, user.id, "Đăng ký", f"Tài khoản '{payload.username}' được tạo.", ip_address)
        email_sent = send_otp_email(payload.email, otp_code, payload.username)
        if not email_sent:
            print(f"\n{'='*50}")
            print(f"[DEV MODE] OTP for {payload.username}: {otp_code}")
            print(f"{'='*50}\n")
        return {
            "status": "success",
            "message": "Đăng ký thành công. Vui lòng kiểm tra email để lấy mã OTP.",
            "user_id": user.id,
            "otp_dev": otp_code if not email_sent else None
        }

    @staticmethod
    def verify_otp(payload, db: Session):
        user = db.query(User).filter(User.username == payload.username).first()
        if not user:
            raise HTTPException(status_code=400, detail="Không tìm thấy tài khoản.")
        if user.is_verified == 1:
            raise HTTPException(status_code=400, detail="Tài khoản đã được xác thực.")
        otp_token = (
            db.query(Token)
            .filter(
                Token.user_id == user.id,
                Token.token == payload.otp,
                Token.type == "email_verify",
                Token.expires_at >= get_vietnam_now()
            )
            .order_by(Token.id.desc())
            .first()
        )
        if not otp_token:
            raise HTTPException(status_code=400, detail="Mã OTP không hợp lệ hoặc đã hết hạn.")
        user.is_verified = 1
        db.delete(otp_token)
        db.commit()
        log_activity(db, user.id, "Xác thực OTP", "Tài khoản đã được xác thực.")
        return {"status": "success", "message": "Xác thực thành công. Bạn có thể đăng nhập."}

    @staticmethod
    def login(payload: UserLogin, db: Session, request=None):
        user = db.query(User).filter(User.username == payload.username).first()
        if not user or not verify_password(user.password_hash, payload.password):
            raise HTTPException(status_code=400, detail="Tên đăng nhập hoặc mật khẩu không đúng.")
        if user.is_verified != 1:
            raise HTTPException(status_code=403, detail="Tài khoản chưa được xác thực OTP.")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa.")
        user.last_login_at = get_vietnam_now()
        db.commit()
        ip_address = ""
        if request:
            ip_address = request.client.host if request.client else ""
        log_activity(db, user.id, "Đăng nhập", "Đăng nhập thành công.", ip_address)
        return {
            "status": "success",
            "message": "Đăng nhập thành công.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_verified": user.is_verified,
                "is_active": user.is_active
            }
        }

    @staticmethod
    def forgot_password(username: str, db: Session):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=400, detail="Không tìm thấy tài khoản.")
        otp_code = generate_otp()
        otp_token = Token(
            user_id=user.id,
            token=otp_code,
            type="password_reset",
            expires_at=get_vietnam_now() + timedelta(minutes=5)
        )
        db.add(otp_token)
        db.commit()
        email_sent = send_otp_email(user.email, otp_code, user.username)
        if not email_sent:
            print(f"\n{'='*50}")
            print(f"[DEV MODE] Password reset OTP for {username}: {otp_code}")
            print(f"{'='*50}\n")
        return {
            "status": "success",
            "message": "Mã OTP khôi phục đã được gửi qua email.",
            "otp_dev": otp_code if not email_sent else None
        }

    @staticmethod
    def reset_password(payload, db: Session):
        user = db.query(User).filter(User.username == payload.username).first()
        if not user:
            raise HTTPException(status_code=400, detail="Không tìm thấy tài khoản.")
        otp_token = (
            db.query(Token)
            .filter(
                Token.user_id == user.id,
                Token.token == payload.otp,
                Token.type == "password_reset",
                Token.expires_at >= get_vietnam_now()
            )
            .order_by(Token.id.desc())
            .first()
        )
        if not otp_token:
            raise HTTPException(status_code=400, detail="Mã OTP không hợp lệ hoặc đã hết hạn.")
        if verify_password(user.password_hash, payload.new_password):
            raise HTTPException(status_code=400, detail="Mật khẩu mới không được trùng mật khẩu cũ.")
        user.password_hash = hash_password(payload.new_password)
        db.delete(otp_token)
        db.commit()
        log_activity(db, user.id, "Đặt lại mật khẩu", "Mật khẩu đã được thay đổi.")
        return {"status": "success", "message": "Đặt lại mật khẩu thành công."}

    @staticmethod
    def logout(user_id: int, db: Session):
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.last_logout_at = get_vietnam_now()
            db.commit()
            log_activity(db, user_id, "Đăng xuất")
        return {"status": "success", "message": "Đăng xuất thành công."}
