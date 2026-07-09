from fastapi import Request, BackgroundTasks
from sqlalchemy.orm import Session
from src.models import schemas
from src.services.auth_service import AuthService

class AuthController:
    @staticmethod
    async def register(user_data: schemas.UserRegister, request: Request, background_tasks: BackgroundTasks, db: Session):
        return await AuthService.register(user_data, request, background_tasks, db)

    @staticmethod
    async def verify_otp(payload: schemas.UserVerifyOTP, db: Session):
        return await AuthService.verify_otp(payload, db)

    @staticmethod
    async def resend_otp(payload: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session):
        return await AuthService.resend_otp(payload, background_tasks, db)

    @staticmethod
    async def login(credentials: schemas.UserLogin, request: Request, db: Session):
        return await AuthService.login(credentials, request, db)

    @staticmethod
    async def forgot_password(payload: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session):
        return await AuthService.forgot_password(payload, background_tasks, db)

    @staticmethod
    async def reset_password(payload: schemas.ResetPasswordRequest, db: Session):
        return await AuthService.reset_password(payload, db)

    @staticmethod
    async def logout(payload: schemas.ForgotPasswordRequest, request: Request, db: Session):
        return await AuthService.logout(payload, request, db)

    @staticmethod
    async def test_email(email: str):
        return await AuthService.test_email(email)
