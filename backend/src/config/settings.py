# Cấu hình hệ thống & Biến môi trường
import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "ANPR PostgreSQL LPR API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Đường dẫn thư mục gốc và thư mục weights
    # settings.py ở src/config/settings.py, do đó cần 3 lần dirname để ra thư mục anpr-backend
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    WEIGHTS_DIR: str = os.getenv("WEIGHTS_DIR", os.path.join(BASE_DIR, "weights"))
    
    # Thiết bị xử lý AI: "cuda" (GPU) hoặc "cpu"
    DEVICE: str = os.getenv("DEVICE", "cuda")

    # Cấu hình Threshold
    CONF_S1_IMG: float = 0.6
    CONF_S2_IMG: float = 0.5
    CONF_S3_IMG: float = 0.3
    
    CONF_S1_VID: float = 0.5
    CONF_S2_VID: float = 0.8
    CONF_S3_VID: float = 0.7
    
    # Kết nối Database PostgreSQL (mặc định nếu không cung cấp)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:18112005@localhost:5432/Web_orc"
    )

    # Cấu hình SMTP gửi Gmail
    # Nếu để trống hoặc không set, hệ thống tự fallback về Dev Mode (OTP in console)
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER", None) or None
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None) or None
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
