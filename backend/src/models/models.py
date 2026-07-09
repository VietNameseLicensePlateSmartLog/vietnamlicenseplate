# Định nghĩa cấu trúc bảng (ORM Models)
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, Date, ForeignKey, SmallInteger, BigInteger
from sqlalchemy.sql import func
from src.config.database import Base

class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default='user')
    is_verified = Column(SmallInteger, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Statistic(Base):
    __tablename__ = "statistics"

    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(Date, nullable=False, unique=True, server_default=func.current_date())
    total_detections = Column(Integer, nullable=False, default=0)
    unique_plates = Column(Integer, nullable=False, default=0)
    avg_confidence = Column(Float, nullable=False, default=0.0)
    correct_count = Column(Integer, nullable=False, default=0)
    incorrect_count = Column(Integer, nullable=False, default=0)
    unverified_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, server_default=func.now())

class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), nullable=False, unique=True, index=True)
    type = Column(String(20), nullable=False)  # 'password_reset' hoặc 'email_verify'
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class VideoJob(Base):
    __tablename__ = "video_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=True)
    duration = Column(Float, nullable=True)
    fps = Column(Float, nullable=True)
    total_frames = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default='pending')
    progress = Column(SmallInteger, nullable=True, default=0)
    current_frame = Column(Integer, nullable=True, default=0)
    error_message = Column(Text, nullable=True)
    output_csv = Column(String(500), nullable=True)
    output_xlsx = Column(String(500), nullable=True)
    output_video = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    plate_text = Column(String(20), nullable=False, index=True)
    plate_confidence = Column(Float, nullable=False)
    alt_text = Column(String(20), nullable=True)
    alt_confidence = Column(Float, nullable=True)
    total_frames = Column(Integer, nullable=True, default=0)
    frame_start = Column(Integer, nullable=True)
    frame_end = Column(Integer, nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id", ondelete="SET NULL"), nullable=True)
    image_path = Column(String(500), nullable=True)
    source_type = Column(String(20), nullable=False, default='camera')
    video_job_id = Column(Integer, ForeignKey("video_jobs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("detections.id", ondelete="CASCADE"), nullable=False)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plate_text = Column(String(20), nullable=False)
    predicted_text = Column(String(20), nullable=False)
    is_correct = Column(SmallInteger, nullable=False)
    verified_at = Column(DateTime, server_default=func.now())
