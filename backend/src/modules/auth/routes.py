from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from src.core.config.database import get_db
from src.modules.auth.schemas import (
    UserRegister, UserLogin, UserVerifyOTP,
    ForgotPasswordRequest, ResetPasswordRequest
)
from src.modules.auth.controller import AuthController
from src.core.utils.email import test_smtp_connection

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register")
async def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    return await AuthController.register(payload, db, request)

@router.post("/verify-otp")
async def verify_otp(payload: UserVerifyOTP, db: Session = Depends(get_db)):
    return await AuthController.verify_otp(payload, db)

@router.post("/login")
async def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    return await AuthController.login(payload, db, request)

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return await AuthController.forgot_password(payload.username, db)

@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    return await AuthController.reset_password(payload, db)

@router.post("/logout")
async def logout(user_id: int, db: Session = Depends(get_db)):
    return await AuthController.logout(user_id, db)

@router.get("/test-email")
async def test_email():
    return test_smtp_connection()
