from datetime import datetime, timedelta
import random
from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models import models, schemas
from src.utils.security import hash_password, verify_password
from src.utils.email import send_otp_email, test_smtp_connection
from src.utils.helpers import log_activity, get_vietnam_now

class AuthService:
    @staticmethod
    async def register(user_data: schemas.UserRegister, request: Request, background_tasks: BackgroundTasks, db: Session):
        username = user_data.username.strip()
        email = user_data.email.strip().lower()
        
        if not username:
            raise HTTPException(status_code=400, detail="Tài khoản không được bỏ trống.")
        if not email:
            raise HTTPException(status_code=400, detail="Email không được bỏ trống.")
            
        hashed = hash_password(user_data.password)
        # Kiểm tra xem tài khoản đã tồn tại chưa
        existing_username = db.query(models.User).filter(models.User.username == username).first()
        if existing_username:
            if existing_username.is_verified == 1:
                raise HTTPException(status_code=400, detail="Tài khoản này đã được đăng ký.")
            else:
                user = existing_username
                user.password_hash = hashed
        else:
            # Kiểm tra xem email đã được tài khoản kích hoạt khác sử dụng chưa
            existing_email = db.query(models.User).filter(models.User.email == email, models.User.is_verified == 1).first()
            if existing_email:
                raise HTTPException(status_code=400, detail="Email này đã được sử dụng bởi tài khoản khác.")
                
            user = models.User(username=username, email=email, password_hash=hashed, role='user', is_verified=0, is_active=True)
            db.add(user)
            db.flush()
            
        user.email = email
        db.commit()
        
        # Sinh OTP 6 số
        otp = "{:06d}".format(random.randint(0, 999999))
        
        # Xóa các token cũ cùng loại của user
        db.query(models.Token).filter(models.Token.user_id == user.id, models.Token.type == 'email_verify').delete()
        
        # Lưu token mới
        db_token = models.Token(
            user_id=user.id,
            token=otp,
            type='email_verify',
            expires_at=get_vietnam_now() + timedelta(minutes=5)
        )
        db.add(db_token)
        db.commit()
        
        is_smtp_configured = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)
        if is_smtp_configured:
            # Gửi email đồng bộ để kiểm tra kết quả
            email_sent = send_otp_email(email, otp)
            if email_sent:
                message = "Mã OTP xác thực đã được gửi về Gmail của bạn."
            else:
                print(f"\n[DEVELOPMENT MODE] Register OTP for {username} ({email}) is: {otp}\n")
                message = f"Gửi email thất bại. [Dev Mode] OTP của bạn là: {otp}"
        else:
            print(f"\n[DEVELOPMENT MODE] OTP code for {username} ({email}) is: {otp}\n")
            message = f"Đăng ký tạm thời thành công. [Dev Mode] OTP của bạn là: {otp}"
            
        client_ip = request.client.host if request.client else ""
        log_activity(db, user.id, "Đăng ký", f"Tài khoản '{username}' đã đăng ký với email {email}.", client_ip)
        
        return {
            "status": "success",
            "message": message,
            "username": username,
            "email": email,
            "dev_mode": not is_smtp_configured
        }

    @staticmethod
    async def verify_otp(payload: schemas.UserVerifyOTP, db: Session):
        username = payload.username.strip()
        otp_code = payload.otp.strip()
        
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy thông tin tài khoản.")
            
        if user.is_verified == 1:
            return {"status": "success", "message": "Tài khoản đã được xác thực trước đó."}
            
        token_record = db.query(models.Token).filter(
            models.Token.user_id == user.id,
            models.Token.token == otp_code,
            models.Token.type == 'email_verify',
            models.Token.is_used == False
        ).first()
        
        if not token_record:
            raise HTTPException(status_code=400, detail="Mã OTP không chính xác.")
            
        if get_vietnam_now().replace(tzinfo=None) > token_record.expires_at:
            raise HTTPException(status_code=400, detail="Mã OTP đã hết hạn. Vui lòng gửi lại mã mới.")
            
        user.is_verified = 1
        user.is_active = True
        token_record.is_used = True
        db.commit()
        
        return {"status": "success", "message": "Kích hoạt tài khoản thành công! Bạn có thể đăng nhập."}

    @staticmethod
    async def resend_otp(payload: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session):
        username = payload.username.strip()
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="Tài khoản chưa được đăng ký.")
        if user.is_verified == 1:
            raise HTTPException(status_code=400, detail="Tài khoản này đã được xác thực.")
            
        otp = "{:06d}".format(random.randint(0, 999999))
        
        db.query(models.Token).filter(models.Token.user_id == user.id, models.Token.type == 'email_verify').delete()
        
        db_token = models.Token(
            user_id=user.id,
            token=otp,
            type='email_verify',
            expires_at=get_vietnam_now() + timedelta(minutes=5)
        )
        db.add(db_token)
        db.commit()
        
        is_smtp_configured = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)
        if is_smtp_configured:
            # Gửi email đồng bộ để kiểm tra kết quả
            email_sent = send_otp_email(user.email, otp)
            if email_sent:
                message = "Mã OTP mới đã được gửi về Gmail của bạn."
            else:
                print(f"\n[DEVELOPMENT MODE] Resent OTP for {username} ({user.email}) is: {otp}\n")
                message = f"Gửi email thất bại. [Dev Mode] OTP mới là: {otp}"
        else:
            print(f"\n[DEVELOPMENT MODE] Resent OTP code for {username} ({user.email}) is: {otp}\n")
            message = f"Gửi lại OTP thành công. [Dev Mode] OTP mới là: {otp}"
            
        return {
            "status": "success",
            "message": message,
            "username": username,
            "email": user.email,
            "dev_mode": not is_smtp_configured
        }

    @staticmethod
    async def login(credentials: schemas.UserLogin, request: Request, db: Session):
        username = credentials.username.strip()
        password = credentials.password
        client_ip = request.client.host if request.client else ""

        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            log_activity(db, None, "Đăng nhập thất bại", f"Tài khoản '{username}' không tồn tại.", client_ip)
            raise HTTPException(status_code=400, detail="Tài khoản hoặc mật khẩu không chính xác.")
            
        if user.is_verified != 1:
            raise HTTPException(status_code=400, detail="Tài khoản chưa được kích hoạt bằng OTP. Vui lòng xác thực trước.")
            
        if not user.is_active:
            log_activity(db, user.id, "Đăng nhập thất bại", f"Tài khoản '{username}' đã bị vô hiệu hóa.", client_ip)
            raise HTTPException(status_code=400, detail="Tài khoản đã bị vô hiệu hóa.")
            
        if not verify_password(password, user.password_hash):
            log_activity(db, user.id, "Đăng nhập thất bại", f"Tài khoản '{username}' nhập sai mật khẩu.", client_ip)
            raise HTTPException(status_code=400, detail="Tài khoản hoặc mật khẩu không chính xác.")

        # Chỉ ghi log đăng nhập khi:
        #   - Lần đầu đăng nhập (last_login_at chưa có), HOẶC
        #   - Đã đăng xuất trước đó (last_logout_at > last_login_at)
        should_log = (
            user.last_login_at is None
            or (
                user.last_logout_at is not None
                and user.last_login_at is not None
                and user.last_logout_at > user.last_login_at
            )
        )

        user.last_login_at = get_vietnam_now().replace(tzinfo=None)
        db.commit()

        if should_log:
            log_activity(db, user.id, "Đăng nhập", f"Tài khoản '{username}' đăng nhập thành công (role: {user.role}).", client_ip)

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
    async def forgot_password(payload: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session):
        username = payload.username.strip()
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="Tài khoản không tồn tại.")

        otp = "{:06d}".format(random.randint(0, 999999))

        db.query(models.Token).filter(models.Token.user_id == user.id, models.Token.type == 'password_reset').delete()

        db_token = models.Token(
            user_id=user.id,
            token=otp,
            type='password_reset',
            expires_at=get_vietnam_now() + timedelta(minutes=5)
        )
        db.add(db_token)
        db.commit()

        is_smtp_configured = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)
        if is_smtp_configured:
            # Gửi email và kiểm tra kết quả
            email_sent = send_otp_email(user.email, otp)
            if email_sent:
                message = "Mã OTP đặt lại mật khẩu đã được gửi về Gmail của tài khoản này."
            else:
                message = f"Gửi email thất bại. [Dev Mode] OTP của bạn là: {otp}"
        else:
            print(f"\n[DEVELOPMENT MODE] Forgot Password OTP for {username} ({user.email}) is: {otp}\n")
            message = f"Yêu cầu thành công. [Dev Mode] OTP đặt lại mật khẩu của bạn là: {otp}"

        return {
            "status": "success",
            "message": message,
            "username": username,
            "email": user.email,
            "dev_mode": not is_smtp_configured
        }

    @staticmethod
    async def reset_password(payload: schemas.ResetPasswordRequest, db: Session):
        username = payload.username.strip()
        otp_code = payload.otp.strip()
        
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản tương ứng.")
            
        token_record = db.query(models.Token).filter(
            models.Token.user_id == user.id,
            models.Token.token == otp_code,
            models.Token.type == 'password_reset',
            models.Token.is_used == False
        ).first()
        
        if not token_record:
            raise HTTPException(status_code=400, detail="Mã OTP không chính xác.")
            
        if get_vietnam_now().replace(tzinfo=None) > token_record.expires_at:
            raise HTTPException(status_code=400, detail="Mã OTP đã hết hạn. Vui lòng yêu cầu gửi lại mã mới.")

        # Kiểm tra mật khẩu mới không được trùng mật khẩu cũ
        if verify_password(payload.new_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Mật khẩu mới không được trùng mật khẩu cũ.")

        user.password_hash = hash_password(payload.new_password)
        token_record.is_used = True
        user.is_verified = 1
        db.commit()
        
        return {"status": "success", "message": "Đặt lại mật khẩu mới thành công! Bạn đã có thể đăng nhập."}

    @staticmethod
    async def logout(payload: schemas.ForgotPasswordRequest, request: Request, db: Session):
        username = payload.username.strip()
        user = db.query(models.User).filter(models.User.username == username).first()
        client_ip = request.client.host if request.client else ""
        if user:
            user.last_logout_at = get_vietnam_now().replace(tzinfo=None)
            db.commit()
            log_activity(db, user.id, "Đăng xuất", f"Tài khoản '{username}' đăng xuất thành công.", client_ip)
        else:
            log_activity(db, None, "Đăng xuất", f"Tài khoản '{username}' (không tồn tại trong DB) đăng xuất.", client_ip)
        return {"status": "success", "message": "Đăng xuất thành công."}

    @staticmethod
    async def test_email(to_email: str):
        """Test gửi email OTP — dùng để debug cấu hình SMTP."""
        is_smtp_configured = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)
        if not is_smtp_configured:
            return {
                "status": "error",
                "message": "SMTP chưa được cấu hình. Điền SMTP_USER và SMTP_PASSWORD trong file backend/.env",
                "smtp_user": settings.SMTP_USER or "(trống)",
                "smtp_server": settings.SMTP_SERVER,
                "smtp_port": settings.SMTP_PORT,
            }

        otp = "123456"  # OTP test
        result = test_smtp_connection(to_email, otp)

        return {
            "status": "success" if result["ok"] else "error",
            "message": result["message"],
            "smtp_user": settings.SMTP_USER,
            "smtp_server": settings.SMTP_SERVER,
            "smtp_port": settings.SMTP_PORT,
        }
