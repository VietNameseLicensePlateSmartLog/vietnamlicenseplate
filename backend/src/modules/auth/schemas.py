from pydantic import BaseModel
from datetime import datetime

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserVerifyOTP(BaseModel):
    username: str
    otp: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_verified: int
    is_active: bool

    class Config:
        from_attributes = True

class ForgotPasswordRequest(BaseModel):
    username: str

class ResetPasswordRequest(BaseModel):
    username: str
    otp: str
    new_password: str
