"""Camera Routes — REST API CRUD + IP camera connection test."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.core.config.database import get_db
from src.modules.camera.controller import CameraController
from src.modules.camera.schemas import CameraCreate, CameraUpdate, CameraTestRequest, CameraTestResponse
from src.modules.camera.service import CameraService

router = APIRouter(tags=["Camera"])


@router.get("/cameras")
async def get_all_cameras(db: Session = Depends(get_db)):
    return CameraController.get_all(db)


@router.get("/cameras/{camera_id}")
async def get_camera(camera_id: int, db: Session = Depends(get_db)):
    return CameraController.get_by_id(db, camera_id)


@router.post("/cameras")
async def create_camera(data: CameraCreate, db: Session = Depends(get_db)):
    return CameraController.create(db, data)


@router.put("/cameras/{camera_id}")
async def update_camera(camera_id: int, data: CameraUpdate, db: Session = Depends(get_db)):
    return CameraController.update(db, camera_id, data)


@router.delete("/cameras/{camera_id}")
async def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    return CameraController.delete(db, camera_id)


@router.post("/cameras/{camera_id}/toggle")
async def toggle_camera(camera_id: int, db: Session = Depends(get_db)):
    return CameraController.toggle_active(db, camera_id)


@router.post("/cameras/reset-all")
async def reset_all_cameras(db: Session = Depends(get_db)):
    """Reset tất cả cameras về trạng thái mặc định."""
    return CameraController.reset_all(db)


@router.post("/cameras/{camera_id}/test", response_model=CameraTestResponse)
async def test_camera_connection(
    camera_id: int,
    data: CameraTestRequest = CameraTestRequest(),
    db: Session = Depends(get_db),
):
    """Test kết nối camera — thử đọc frames trong vài giây.

    Nếu body có rtsp_url thì dùng URL đó (cho test trước khi save).
    Nếu không, lấy URL từ camera record trong DB.
    """
    return await CameraService.test_connection(db, camera_id, data)


@router.post("/cameras/test-url", response_model=CameraTestResponse)
async def test_camera_url(data: CameraTestRequest, db: Session = Depends(get_db)):
    """Test kết nối từ URL mới (chưa cần save camera)."""
    return await CameraService.test_connection(db, None, data)
