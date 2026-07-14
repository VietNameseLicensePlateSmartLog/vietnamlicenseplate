"""Pydantic schemas cho Camera CRUD operations."""
from pydantic import BaseModel
from datetime import datetime


class CameraCreate(BaseModel):
    name: str
    rtsp_url: str
    stream_url: str | None = None
    region_id: int | None = None
    fps_target: int = 10
    description: str | None = None


class CameraUpdate(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None
    stream_url: str | None = None
    region_id: int | None = None
    is_active: bool | None = None
    fps_target: int | None = None
    description: str | None = None


class CameraResponse(BaseModel):
    id: int
    name: str
    rtsp_url: str
    stream_url: str | None = None
    region_id: int | None
    is_active: bool
    is_online: bool
    fps_target: int
    description: str | None
    created_at: datetime | None
    updated_at: datetime | None
    region_name: str | None = None

    model_config = {"from_attributes": True}
