"""Camera Service — business logic cho CRUD camera + IP camera connection."""
import asyncio
import logging
import cv2
from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.modules.camera.models import Camera
from src.modules.camera.schemas import CameraCreate, CameraUpdate, CameraTestRequest
from src.modules.region.models import Region

logger = logging.getLogger(__name__)


def _camera_to_dict(cam: Camera, region_name: str | None = None) -> dict:
    """Chuyển Camera ORM object → dict (bao gồm cả IP connection fields)."""
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
        # IP Camera connection fields
        "stream_type": cam.stream_type or "rtsp",
        "username": cam.username,
        "connect_timeout": cam.connect_timeout or 10,
        "reconnect_interval": cam.reconnect_interval or 5,
        "max_reconnect_attempts": cam.max_reconnect_attempts or 10,
        "last_connected_at": cam.last_connected_at,
        "last_error": cam.last_error,
    }


def _resolve_region_name(db: Session, region_id: int | None) -> str | None:
    """Resolve region ID → name."""
    if not region_id:
        return None
    region = db.query(Region).filter(Region.id == region_id).first()
    return region.name if region else None


class CameraService:

    @staticmethod
    def get_all(db: Session) -> list[dict]:
        """Lấy danh sách tất cả cameras kèm tên region."""
        cameras = db.query(Camera).order_by(Camera.id).all()
        return [
            _camera_to_dict(cam, _resolve_region_name(db, cam.region_id))
            for cam in cameras
        ]

    @staticmethod
    def get_by_id(db: Session, camera_id: int) -> dict:
        """Lấy thông tin 1 camera theo ID."""
        cam = db.query(Camera).filter(Camera.id == camera_id).first()
        if not cam:
            raise HTTPException(status_code=404, detail="Không tìm thấy camera.")
        return _camera_to_dict(cam, _resolve_region_name(db, cam.region_id))

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
            # IP Camera connection fields
            stream_type=data.stream_type,
            username=data.username,
            password_encrypted=data.password,  # TODO: Fernet encrypt
            connect_timeout=data.connect_timeout,
            reconnect_interval=data.reconnect_interval,
            max_reconnect_attempts=data.max_reconnect_attempts,
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)

        return _camera_to_dict(camera)

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

        # Map 'password' → 'password_encrypted' khi update
        if "password" in update_data:
            update_data["password_encrypted"] = update_data.pop("password")

        for key, value in update_data.items():
            setattr(camera, key, value)

        db.commit()
        db.refresh(camera)

        return _camera_to_dict(camera, _resolve_region_name(db, camera.region_id))

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
        """Bật/tắt camera (is_active)."""
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

    @staticmethod
    async def test_connection(db: Session, camera_id: int | None, data: CameraTestRequest) -> dict:
        """Test kết nối camera — thử đọc frames trong vài giây.

        Nếu camera_id có sẵn thì test từ DB, nếu data có rtsp_url thì test URL đó.
        """
        # Xác định URL để test
        rtsp_url = data.rtsp_url
        stream_type = data.stream_type or "rtsp"
        username = data.username
        password = data.password
        timeout = data.connect_timeout or 10

        if camera_id:
            cam = db.query(Camera).filter(Camera.id == camera_id).first()
            if not cam:
                raise HTTPException(status_code=404, detail="Không tìm thấy camera.")
            rtsp_url = rtsp_url or cam.rtsp_url
            stream_type = stream_type or cam.stream_type or "rtsp"
            username = username or cam.username
            password = password or cam.password_encrypted

        if not rtsp_url:
            return {"success": False, "message": "Chưa có URL kết nối camera."}

        # Build URL với auth
        from src.modules.camera.connection_manager import build_stream_url, auto_fix_url
        from types import SimpleNamespace

        fake_camera = SimpleNamespace(
            rtsp_url=rtsp_url,
            username=username,
            password_encrypted=password,
            stream_type=stream_type,
        )
        full_url = build_stream_url(fake_camera)
        full_url = auto_fix_url(full_url, stream_type)

        # Test kết nối
        cap = None
        try:
            cap = await asyncio.to_thread(cv2.VideoCapture, full_url)
            if not cap or not cap.isOpened():
                return {
                    "success": False,
                    "message": f"Không thể mở kết nối: {full_url}. Kiểm tra IP, port, và authentication.",
                }

            # Set timeout
            timeout_ms = timeout * 1000
            try:
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
            except Exception:
                pass

            # Đọc 3 frames để test FPS
            frames_read = 0
            resolution = None
            start_time = asyncio.get_event_loop().time()

            for _ in range(3):
                ret, frame = await asyncio.to_thread(cap.read)
                if ret and frame is not None:
                    frames_read += 1
                    if resolution is None:
                        h, w = frame.shape[:2]
                        resolution = f"{w}x{h}"
                    await asyncio.sleep(0.2)  # Đợi 200ms giữa các frame
                else:
                    break

            elapsed = asyncio.get_event_loop().time() - start_time

            if frames_read == 0:
                return {
                    "success": False,
                    "message": f"Kết nối thành công nhưng không đọc được frame. URL: {full_url}",
                }

            fps = round(frames_read / elapsed, 1) if elapsed > 0 else 0
            return {
                "success": True,
                "message": f"Kết nối thành công! Resolution: {resolution}, FPS: ~{fps}",
                "fps": fps,
                "resolution": resolution,
                "stream_type": stream_type,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Lỗi kết nối: {str(e)}",
            }
        finally:
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass
