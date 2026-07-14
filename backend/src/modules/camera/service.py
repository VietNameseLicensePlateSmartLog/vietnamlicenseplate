"""Camera Service — business logic cho CRUD camera."""
import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.modules.camera.models import Camera
from src.modules.camera.schemas import CameraCreate, CameraUpdate
from src.modules.region.models import Region

logger = logging.getLogger(__name__)


class CameraService:

    @staticmethod
    def get_all(db: Session) -> list[dict]:
        """Lấy danh sách tất cả cameras kèm tên region."""
        cameras = db.query(Camera).order_by(Camera.id).all()
        result = []
        for cam in cameras:
            region_name = None
            if cam.region_id:
                region = db.query(Region).filter(Region.id == cam.region_id).first()
                region_name = region.name if region else None
            cam_dict = {
                "id": cam.id,
                "name": cam.name,
                "rtsp_url": cam.rtsp_url,
                "stream_url": cam.stream_url,
                "region_id": cam.region_id,
                "is_active": cam.is_active,
                "is_online": cam.is_online,
                "fps_target": cam.fps_target,
                "description": cam.description,
                "created_at": cam.created_at,
                "updated_at": cam.updated_at,
                "region_name": region_name,
            }
            result.append(cam_dict)
        return result

    @staticmethod
    def get_by_id(db: Session, camera_id: int) -> dict:
        """Lấy thông tin 1 camera theo ID."""
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Không tìm thấy camera.")
        region_name = None
        if cam.region_id:
            region = db.query(Region).filter(Region.id == cam.region_id).first()
            region_name = region.name if region else None
        return {
            "id": cam.id,
            "name": cam.name,
            "rtsp_url": cam.rtsp_url,
            "stream_url": cam.stream_url,
            "region_id": cam.region_id,
            "is_active": cam.is_active,
            "is_online": cam.is_online,
            "fps_target": cam.fps_target,
            "description": cam.description,
            "created_at": cam.created_at,
            "updated_at": cam.updated_at,
            "region_name": region_name,
        }

    @staticmethod
    def create(db: Session, data: CameraCreate) -> dict:
        """Tạo camera mới."""
        if data.region_id:
            region = db.query(Region).filter(Region.id == data.region_id).first()
            if not region:
                raise HTTPException(status_code=400, detail="Region không tồn tại.")

        camera = Camera(
            name=data.name,
            rtsp_url=data.rtsp_url,
            stream_url=data.stream_url,
            region_id=data.region_id,
            fps_target=data.fps_target,
            description=data.description,
            is_active=True,
            is_online=False,
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)

        return {
            "id": camera.id,
            "name": camera.name,
            "rtsp_url": camera.rtsp_url,
            "stream_url": camera.stream_url,
            "region_id": camera.region_id,
            "is_active": camera.is_active,
            "is_online": camera.is_online,
            "fps_target": camera.fps_target,
            "description": camera.description,
            "created_at": camera.created_at,
            "updated_at": camera.updated_at,
            "region_name": None,
        }

    @staticmethod
    def update(db: Session, camera_id: int, data: CameraUpdate) -> dict:
        """Cập nhật camera."""
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Không tìm thấy camera.")

        if data.region_id is not None:
            region = db.query(Region).filter(Region.id == data.region_id).first()
            if not region:
                raise HTTPException(status_code=400, detail="Region không tồn tại.")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(camera, key, value)

        db.commit()
        db.refresh(camera)

        region_name = None
        if camera.region_id:
            region = db.query(Region).filter(Region.id == camera.region_id).first()
            region_name = region.name if region else None

        return {
            "id": camera.id,
            "name": camera.name,
            "rtsp_url": camera.rtsp_url,
            "stream_url": camera.stream_url,
            "region_id": camera.region_id,
            "is_active": camera.is_active,
            "is_online": camera.is_online,
            "fps_target": camera.fps_target,
            "description": camera.description,
            "created_at": camera.created_at,
            "updated_at": camera.updated_at,
            "region_name": region_name,
        }

    @staticmethod
    def delete(db: Session, camera_id: int):
        """Xóa camera."""
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Không tìm thấy camera.")
        db.delete(camera)
        db.commit()
        return {"message": "Đã xóa camera thành công."}

    @staticmethod
    def toggle_active(db: Session, camera_id: int) -> dict:
        """Bật/tắt camera (is_active) — chỉ toggle trong DB, không start/stop stream."""
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Không tìm thấy camera.")
        camera.is_active = not camera.is_active
        db.commit()
        db.refresh(camera)
        return {
            "id": camera.id,
            "name": camera.name,
            "is_active": camera.is_active,
            "is_online": camera.is_online,
            "message": f"Camera đã {'bật' if camera.is_active else 'tắt'}.",
        }

    @staticmethod
    def reset_all(db: Session) -> dict:
        """Reset tất cả cameras về trạng thái mặc định."""
        cameras = db.query(Camera).all()
        for cam in cameras:
            cam.is_active = False
            cam.is_online = False
            cam.rtsp_url = ""
        db.commit()
        return {
            "message": f"Đã reset {len(cameras)} cameras.",
            "total": len(cameras),
        }
