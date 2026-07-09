# Định nghĩa kiểu dữ liệu đầu vào/đầu ra (Pydantic)
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class DetectionBase(BaseModel):
    plate_text: str
    plate_confidence: float
    alt_text: Optional[str] = None
    alt_confidence: Optional[float] = None
    image_path: Optional[str] = None
    source_type: str = "camera"

class DetectionCreate(DetectionBase):
    pass

class DetectionResponse(DetectionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True  # Tương thích Pydantic V2 để chuyển đổi ORM -> Pydantic Model

class PlatePrediction(BaseModel):
    bbox: List[int]
    text: str
    conf: float

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


class AdminCreateUser(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"


class AdminUpdateRole(BaseModel):
    role: str
