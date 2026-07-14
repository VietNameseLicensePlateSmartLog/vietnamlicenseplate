import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Vietnam LPR - Nhận diện Biển số xe Việt Nam"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # Thiết bị xử lý AI: "cuda" (GPU) hoặc "cpu"
    DEVICE: str = os.getenv("DEVICE", "cuda")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/Web_orc")

    SMTP_USER: str = os.getenv("SMTP_USER", "vietc3k49@gmail.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))

    CONF_S1_IMG: float = float(os.getenv("CONF_S1_IMG", "0.4"))
    CONF_S2_IMG: float = float(os.getenv("CONF_S2_IMG", "0.3"))
    CONF_S3_IMG: float = float(os.getenv("CONF_S3_IMG", "0.5"))

    CONF_S1_VID: float = float(os.getenv("CONF_S1_VID", "0.4"))
    CONF_S2_VID: float = float(os.getenv("CONF_S2_VID", "0.3"))
    CONF_S3_VID: float = float(os.getenv("CONF_S3_VID", "0.4"))

    WEIGHTS_DIR: str = os.getenv("WEIGHTS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "weights"))

    # Cloudinary — lưu trữ ảnh snapshot trên cloud
    # Nếu không cấu hình → fallback về local static/snapshots/
    CLOUDINARY_URL: str = os.getenv("CLOUDINARY_URL", "")  # format: cloudinary://key:secret@cloud_name
    CLOUDINARY_FOLDER: str = os.getenv("CLOUDINARY_FOLDER", "anpr-snapshots")

settings = Settings()
