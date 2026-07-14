from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from src.core.config.database import Base

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    action = Column(String(100), nullable=False)
    detail = Column(String(500))
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
