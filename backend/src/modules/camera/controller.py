"""Camera Controller — thin delegation → CameraService."""
from sqlalchemy.orm import Session
from src.modules.camera.service import CameraService
from src.modules.camera.schemas import CameraCreate, CameraUpdate


class CameraController:

    @staticmethod
    def get_all(db: Session):
        return CameraService.get_all(db)

    @staticmethod
    def get_by_id(db: Session, camera_id: int):
        return CameraService.get_by_id(db, camera_id)

    @staticmethod
    def create(db: Session, data: CameraCreate):
        return CameraService.create(db, data)

    @staticmethod
    def update(db: Session, camera_id: int, data: CameraUpdate):
        return CameraService.update(db, camera_id, data)

    @staticmethod
    def delete(db: Session, camera_id: int):
        return CameraService.delete(db, camera_id)

    @staticmethod
    def toggle_active(db: Session, camera_id: int):
        return CameraService.toggle_active(db, camera_id)

    @staticmethod
    def reset_all(db: Session):
        return CameraService.reset_all(db)
