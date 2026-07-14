from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from datetime import datetime
from src.core.config.database import Base

class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    plate_text = Column(String(20), nullable=False)
    plate_confidence = Column(Float, default=0.0)
    alt_text = Column(String(20))
    alt_confidence = Column(Float)
    total_frames = Column(Integer, default=1)
    frame_start = Column(Integer)
    frame_end = Column(Integer)
    image_path = Column(String(500))
    source_type = Column(String(20), default="camera")
    user_id = Column(Integer)
    region_id = Column(Integer)
    video_job_id = Column(Integer)
    camera_id = Column(Integer, nullable=True)  # FK → cameras.id (cho nguồn camera realtime)
    created_at = Column(DateTime, default=datetime.utcnow)

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("detections.id"))
    plate_text = Column(String(20), nullable=False)
    predicted_text = Column(String(20), nullable=False)
    is_correct = Column(Integer)
    correct_plate = Column(String(20))
    verified_by = Column(Integer)
    verified_at = Column(DateTime)

class VideoJob(Base):
    __tablename__ = "video_jobs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    filename = Column(String(255))
    file_path = Column(String(500))
    file_size = Column(Integer)
    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)
    current_frame = Column(Integer, default=0)
    total_frames = Column(Integer, default=0)
    fps = Column(Float)
    duration = Column(Float)
    output_video = Column(String(500))
    output_csv = Column(String(500))
    output_xlsx = Column(String(500))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class Statistics(Base):
    __tablename__ = "statistics"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime)
    total_detections = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)
    correct = Column(Integer, default=0)
    incorrect = Column(Integer, default=0)
