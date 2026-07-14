from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from src.core.config.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    is_verified = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    failed_attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime)
    last_logout_at = Column(DateTime)

class Token(Base):
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    token = Column(String(10), nullable=False)
    type = Column(String(20), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
