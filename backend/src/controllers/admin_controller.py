from typing import Optional
from sqlalchemy.orm import Session
from src.models import schemas
from src.services.admin_service import AdminService

class AdminController:
    @staticmethod
    def admin_dashboard_stats(db: Session):
        return AdminService.admin_dashboard_stats(db)

    @staticmethod
    def admin_list_users(db: Session):
        return AdminService.admin_list_users(db)

    @staticmethod
    def admin_toggle_user_active(user_id: int, db: Session):
        return AdminService.admin_toggle_user_active(user_id, db)

    @staticmethod
    def admin_unverified_detections(skip: int, limit: int, db: Session):
        return AdminService.admin_unverified_detections(skip, limit, db)

    @staticmethod
    def admin_verify_detection(detection_id: int, correct_plate: str, is_correct: int, verified_by: int, db: Session):
        return AdminService.admin_verify_detection(detection_id, correct_plate, is_correct, verified_by, db)

    @staticmethod
    def admin_search_detections(
        plate: Optional[str],
        source_type: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        verified: Optional[str],
        region_id: Optional[int],
        skip: int,
        limit: int,
        db: Session
    ):
        return AdminService.admin_search_detections(plate, source_type, date_from, date_to, verified, region_id, skip, limit, db)

    @staticmethod
    def admin_regions_stats(db: Session):
        return AdminService.admin_regions_stats(db)

    @staticmethod
    def admin_activity_logs(skip: int, limit: int, db: Session):
        return AdminService.admin_activity_logs(skip, limit, db)

    @staticmethod
    def admin_create_user(payload: schemas.AdminCreateUser, db: Session):
        return AdminService.admin_create_user(payload.username, payload.email, payload.password, payload.role, db)

    @staticmethod
    def admin_update_user_role(user_id: int, payload: schemas.AdminUpdateRole, db: Session):
        return AdminService.admin_update_user_role(user_id, payload.role, db)

    @staticmethod
    def admin_delete_user(user_id: int, db: Session):
        return AdminService.admin_delete_user(user_id, db)
