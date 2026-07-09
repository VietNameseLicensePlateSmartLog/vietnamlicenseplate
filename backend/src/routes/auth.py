from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import schemas
from src.controllers.auth_controller import AuthController

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
async def register(user_data: schemas.UserRegister, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return await AuthController.register(user_data, request, background_tasks, db)

@router.post("/verify-otp")
async def verify_otp(payload: schemas.UserVerifyOTP, db: Session = Depends(get_db)):
    return await AuthController.verify_otp(payload, db)

@router.post("/resend-otp")
async def resend_otp(payload: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return await AuthController.resend_otp(payload, background_tasks, db)

@router.post("/login")
async def login(credentials: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    return await AuthController.login(credentials, request, db)

@router.post("/forgot-password")
async def forgot_password(payload: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return await AuthController.forgot_password(payload, background_tasks, db)

@router.post("/reset-password")
async def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    return await AuthController.reset_password(payload, db)

@router.post("/logout")
async def logout(payload: schemas.ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    return await AuthController.logout(payload, request, db)

@router.post("/test-email")
async def test_email(email: str = "test@gmail.com"):
    """Test gửi email OTP — dùng debug khi SMTP không hoạt động."""
    return await AuthController.test_email(email)
