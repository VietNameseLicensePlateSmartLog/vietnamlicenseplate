from typing import Optional
from sqlalchemy.orm import Session
from src.modules.admin.schemas import AdminCreateUser, AdminUpdateRole
from src.modules.admin.service import AdminService

class AdminController:
    @staticmethod
    def admin_dashboard_stats(db: Session):
        return AdminService.admin_dashboard_stats(db)

    @staticmethod
    def admin_list_users(db: Session):
        return AdminService.admin_list_users(db)

    @staticmethod
    def get_user_activity(user_id: int, skip: int, limit: int, db: Session):
        return AdminService.get_user_activity(user_id, db, skip, limit)

    @staticmethod
    def admin_toggle_user_active(user_id: int, db: Session):
        return AdminService.admin_toggle_user_active(user_id, db)

    @staticmethod
    def admin_unverified_detections(skip: int, limit: int, db: Session):
        return AdminService.admin_unverified_detections(db, skip, limit)

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
        min_confidence: Optional[float],
        max_confidence: Optional[float],
        skip: int,
        limit: int,
        db: Session
    ):
        return AdminService.admin_search_detections(db, plate, source_type, date_from, date_to, verified, min_confidence, max_confidence, skip, limit)

    @staticmethod
    def admin_regions_stats(db: Session):
        return AdminService.admin_regions_stats(db)

    @staticmethod
    def admin_activity_logs(skip: int, limit: int, db: Session):
        return AdminService.admin_activity_logs(db, skip, limit)

    @staticmethod
    def admin_create_user(payload: AdminCreateUser, db: Session):
        return AdminService.admin_create_user(payload.username, payload.email, payload.password, payload.role, db)

    @staticmethod
    def admin_update_user_role(user_id: int, payload: AdminUpdateRole, db: Session):
        return AdminService.admin_update_user_role(user_id, payload.role, db)

    @staticmethod
    def admin_delete_user(user_id: int, db: Session):
        return AdminService.admin_delete_user(user_id, db)

    @staticmethod
    def admin_delete_detection(detection_id: int, db: Session):
        return AdminService.admin_delete_detection(detection_id, db)

    @staticmethod
    def admin_incorrect_detections(skip: int, limit: int, db: Session):
        return AdminService.admin_incorrect_detections(db, skip, limit)
