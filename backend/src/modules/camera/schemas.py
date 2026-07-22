"""Pydantic schemas cho Camera CRUD + IP Camera connection operations."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    rtsp_url: str = Field(..., min_length=1, max_length=500)
    stream_url: Optional[str] = None
    region_id: Optional[int] = None
    fps_target: int = Field(default=10, ge=1, le=30)
    description: Optional[str] = None
    # IP Camera connection fields
    stream_type: str = Field(default="rtsp", pattern=r"^(rtsp|http|rtmp)$")
    username: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, max_length=200)
    connect_timeout: int = Field(default=10, ge=3, le=60)
    reconnect_interval: int = Field(default=5, ge=1, le=60)
    max_reconnect_attempts: int = Field(default=10, ge=0, le=100)


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    rtsp_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    stream_url: Optional[str] = None
    region_id: Optional[int] = None
    fps_target: Optional[int] = Field(default=None, ge=1, le=30)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    # IP Camera connection fields
    stream_type: Optional[str] = Field(default=None, pattern=r"^(rtsp|http|rtmp)$")
    username: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, max_length=200)
    connect_timeout: Optional[int] = Field(default=None, ge=3, le=60)
    reconnect_interval: Optional[int] = Field(default=None, ge=1, le=60)
    max_reconnect_attempts: Optional[int] = Field(default=None, ge=0, le=100)


class CameraResponse(BaseModel):
    id: int
    name: str
    rtsp_url: str
    stream_url: Optional[str] = None
    region_id: Optional[int] = None
    is_active: bool
    is_online: bool
    fps_target: int
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    region_name: Optional[str] = None
    # IP Camera connection fields
    stream_type: str = "rtsp"
    username: Optional[str] = None
    connect_timeout: int = 10
    reconnect_interval: int = 5
    max_reconnect_attempts: int = 10
    last_connected_at: Optional[datetime] = None
    last_error: Optional[str] = None

    model_config = {"from_attributes": True}


class CameraTestRequest(BaseModel):
    """Request body cho camera test endpoint."""
    rtsp_url: Optional[str] = None       # URL vừa nhập (chưa save) — ưu tiên hơn DB
    stream_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connect_timeout: int = 10


class CameraTestResponse(BaseModel):
    """Response cho camera test endpoint."""
    success: bool
    message: str
    fps: Optional[float] = None
    resolution: Optional[str] = None
    stream_type: Optional[str] = None
