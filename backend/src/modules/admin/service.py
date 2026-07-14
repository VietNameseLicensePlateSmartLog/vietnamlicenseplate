from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import func as sa_func, cast, Date as SADate, extract
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.modules.auth.models import User
from src.modules.detection.models import Detection, Prediction, VideoJob
from src.modules.region.models import Region
from src.modules.camera.models import Camera
from src.modules.admin.models import ActivityLog
from src.core.utils.helpers import log_activity, get_vietnam_now, to_naive_vn
from src.core.utils.security import hash_password

class AdminService:
    @staticmethod
    def admin_dashboard_stats(db: Session):
        total_users = db.query(sa_func.count(User.id)).scalar() or 0
        total_detections = db.query(sa_func.count(Detection.id)).scalar() or 0
        total_verified = db.query(sa_func.count(Prediction.id)).scalar() or 0
        unverified = total_detections - total_verified

        correct = db.query(sa_func.count(Prediction.id)).filter(Prediction.is_correct == 1).scalar() or 0
        incorrect = db.query(sa_func.count(Prediction.id)).filter(Prediction.is_correct == 0).scalar() or 0
        accuracy = round((correct / (correct + incorrect)) * 100, 1) if (correct + incorrect) > 0 else 0.0

        seven_days_ago = to_naive_vn(get_vietnam_now() - timedelta(days=7))
        daily_rows = db.query(
            cast(Detection.created_at, SADate).label("day"),
            sa_func.count(Detection.id).label("count")
        ).filter(
            Detection.created_at >= seven_days_ago
        ).group_by("day").order_by("day").all()

        daily_chart = [{"date": str(row.day), "count": row.count} for row in daily_rows]

        source_rows = db.query(
            Detection.source_type,
            sa_func.count(Detection.id).label("count")
        ).group_by(Detection.source_type).all()
        source_chart = [{"source": row.source_type, "count": row.count} for row in source_rows]

        region_stats = (
            db.query(
                Region.id,
                Region.name,
                sa_func.avg(Detection.plate_confidence).label("avg_confidence"),
                sa_func.count(Detection.id).label("total")
            )
            .outerjoin(Detection, Detection.region_id == Region.id)
            .group_by(Region.id, Region.name)
            .all()
        )
        regions_stats = [
            {
                "id": r.id,
                "name": r.name,
                "avg_confidence": round(float(r.avg_confidence), 4) if r.avg_confidence else 0.0,
                "total": r.total
            }
            for r in region_stats
        ]

        total_regions = db.query(sa_func.count(Region.id)).scalar() or 0

        # Top plates — top 10 biển số nhận diện nhiều nhất
        top_plate_rows = (
            db.query(
                Detection.plate_text.label("plate"),
                sa_func.count(Detection.id).label("count")
            )
            .filter(Detection.plate_text.isnot(None), Detection.plate_text != "")
            .group_by(Detection.plate_text)
            .order_by(sa_func.count(Detection.id).desc())
            .limit(10)
            .all()
        )
        top_plates = [{"plate": r.plate, "count": r.count} for r in top_plate_rows]

        # Confidence distribution — phân bố theo khoảng confidence
        conf_ranges = [
            ("90-100%", 0.9, 1.01),
            ("70-89%", 0.7, 0.9),
            ("50-69%", 0.5, 0.7),
            ("Dưới 50%", 0.0, 0.5),
        ]
        conf_distribution = []
        for label, low, high in conf_ranges:
            cnt = db.query(sa_func.count(Detection.id)).filter(
                Detection.plate_confidence >= low,
                Detection.plate_confidence < high
            ).scalar() or 0
            conf_distribution.append({"label": label, "count": cnt})

        # Average confidence
        avg_conf = db.query(sa_func.avg(Detection.plate_confidence)).scalar()
        avg_confidence = round(float(avg_conf) * 100, 1) if avg_conf else 0.0

        return {
            "total_users": total_users,
            "total_detections": total_detections,
            "total_verified": total_verified,
            "unverified": unverified,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": accuracy,
            "avg_confidence": avg_confidence,
            "daily_chart": daily_chart,
            "source_chart": source_chart,
            "top_plates": top_plates,
            "conf_distribution": conf_distribution,
            "regions_stats": regions_stats,
            "total_regions": total_regions,
        }

    @staticmethod
    def admin_list_users(db: Session):
        users = db.query(User).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "is_verified": u.is_verified,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ]

    @staticmethod
    def get_user_activity(user_id: int, db: Session, skip: int = 0, limit: int = 15):
        """Lấy lịch sử hoạt động nhận diện của user — nhóm theo ngày + nguồn."""
        # Kiểm tra user tồn tại
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

        # Query detections của user, nhóm theo ngày + source_type
        activity_query = db.query(
            cast(Detection.created_at, SADate).label("day"),
            Detection.source_type.label("source_type"),
            sa_func.count(Detection.id).label("detection_count"),
            sa_func.avg(Detection.plate_confidence).label("avg_confidence"),
        ).filter(
            Detection.user_id == user_id
        ).group_by(
            "day", "source_type"
        ).order_by(
            sa_func.max(Detection.created_at).desc()
        )

        total = activity_query.count()
        rows = activity_query.offset(skip).limit(limit).all()

        return {
            "total": total,
            "items": [
                {
                    "date": str(row.day),
                    "source_type": row.source_type,
                    "detection_count": row.detection_count,
                    "avg_confidence": round(float(row.avg_confidence), 4) if row.avg_confidence else 0.0,
                }
                for row in rows
            ],
        }

    @staticmethod
    def admin_toggle_user_active(user_id: int, db: Session):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
        if user.username == "abc1":
            raise HTTPException(status_code=400, detail="Không thể vô hiệu hóa tài khoản admin mặc định.")
        user.is_active = not user.is_active
        db.commit()
        status = "kích hoạt" if user.is_active else "vô hiệu hóa"
        log_activity(db, None, f"Admin {status} tài khoản", f"Đã {status} tài khoản '{user.username}'")
        return {"status": "success", "is_active": user.is_active}

    @staticmethod
    def admin_unverified_detections(db: Session, skip: int = 0, limit: int = 30):
        from src.modules.detection.models import Prediction
        verified_ids = db.query(Prediction.detection_id).subquery()
        unverified = (
            db.query(Detection)
            .filter(~Detection.id.in_(db.query(verified_ids)))
            .order_by(Detection.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": d.id,
                "plate_text": d.plate_text,
                "plate_confidence": d.plate_confidence,
                "alt_text": d.alt_text,
                "alt_confidence": d.alt_confidence,
                "total_frames": d.total_frames,
                "image_path": d.image_path,
                "source_type": d.source_type,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in unverified
        ]

    @staticmethod
    def admin_verify_detection(detection_id: int, correct_plate: str, is_correct: int, verified_by: int, db: Session):
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên nhận diện.")
        existing = db.query(Prediction).filter(Prediction.detection_id == detection_id).first()
        if existing:
            existing.is_correct = is_correct
            existing.correct_plate = correct_plate
            existing.plate_text = detection.plate_text
            existing.predicted_text = detection.plate_text
            existing.verified_by = verified_by
            existing.verified_at = get_vietnam_now()
        else:
            prediction = Prediction(
                detection_id=detection_id,
                plate_text=detection.plate_text,
                predicted_text=detection.plate_text,
                is_correct=is_correct,
                correct_plate=correct_plate,
                verified_by=verified_by,
                verified_at=get_vietnam_now()
            )
            db.add(prediction)
        db.commit()
        return {"status": "success", "message": "Đã xác minh kết quả."}

    @staticmethod
    def admin_delete_detection(detection_id: int, db: Session):
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên nhận diện.")
        db.query(Prediction).filter(Prediction.detection_id == detection_id).delete()
        db.delete(detection)
        db.commit()
        return {"status": "success", "message": "Đã xóa phiên nhận diện."}

    @staticmethod
    def admin_search_detections(
        db: Session,
        plate: Optional[str] = None,
        source_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        verified: Optional[str] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        skip: int = 0,
        limit: int = 50
    ):
        query = db.query(Detection)
        if plate:
            query = query.filter(Detection.plate_text.ilike(f"%{plate}%"))
        if source_type:
            query = query.filter(Detection.source_type == source_type)
        if date_from:
            query = query.filter(Detection.created_at >= date_from)
        if date_to:
            query = query.filter(Detection.created_at <= date_to + " 23:59:59")
        if min_confidence is not None:
            query = query.filter(Detection.plate_confidence >= min_confidence)
        if max_confidence is not None:
            query = query.filter(Detection.plate_confidence <= max_confidence)
        query = query.order_by(Detection.created_at.desc())
        total = query.count()
        detections = query.offset(skip).limit(limit).all()

        # Pre-load camera names cho hiệu quả
        camera_ids = [d.camera_id for d in detections if d.camera_id]
        camera_map = {}
        if camera_ids:
            cameras = db.query(Camera).filter(Camera.id.in_(camera_ids)).all()
            camera_map = {c.id: c.name for c in cameras}

        results = []
        for d in detections:
            item = {
                "id": d.id,
                "plate_text": d.plate_text,
                "plate_confidence": d.plate_confidence,
                "image_path": d.image_path,
                "source_type": d.source_type,
                "camera_id": d.camera_id,
                "camera_name": camera_map.get(d.camera_id) if d.camera_id else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "verified": None
            }
            pred = db.query(Prediction).filter(Prediction.detection_id == d.id).first()
            if pred:
                item["verified"] = pred.is_correct
            results.append(item)

        if verified is not None:
            if verified == "true":
                results = [r for r in results if r["verified"] == 1]
            elif verified == "false":
                results = [r for r in results if r["verified"] == 0]
            elif verified == "none":
                results = [r for r in results if r["verified"] is None]

        return {"total": total, "items": results}

    @staticmethod
    def admin_regions_stats(db: Session):
        regions = db.query(Region).all()
        results = []
        for region in regions:
            count = db.query(sa_func.count(Detection.id)).filter(Detection.region_id == region.id).scalar() or 0
            avg_conf = db.query(sa_func.avg(Detection.plate_confidence)).filter(Detection.region_id == region.id).scalar()
            results.append({
                "id": region.id,
                "name": region.name,
                "location": region.location,
                "total_detections": count,
                "avg_confidence": round(float(avg_conf), 4) if avg_conf else 0.0
            })
        return results

    @staticmethod
    def admin_activity_logs(db: Session, skip: int = 0, limit: int = 100):
        logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).offset(skip).limit(limit).all()
        results = []
        for log in logs:
            user_email = None
            if log.user_id:
                user = db.query(User).filter(User.id == log.user_id).first()
                if user:
                    user_email = user.email
            results.append({
                "id": log.id,
                "user_id": log.user_id,
                "user_email": user_email,
                "action": log.action,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })
        return results

    @staticmethod
    def admin_create_user(username: str, email: str, password: str, role: str, db: Session):
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại.")
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail="Email đã được sử dụng.")
        user = User(
            username=username,
            email=email,
            full_name=username,
            password_hash=hash_password(password),
            role=role,
            is_verified=1,
            is_active=True,
            failed_attempts=0
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        log_activity(db, None, "Admin tạo tài khoản", f"Đã tạo tài khoản '{username}' với vai trò '{role}'")
        return {"status": "success", "message": f"Đã tạo tài khoản '{username}'."}

    @staticmethod
    def admin_update_user_role(user_id: int, role: str, db: Session):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
        if user.username == "abc1":
            raise HTTPException(status_code=400, detail="Không thể thay đổi vai trò admin mặc định.")
        user.role = role
        db.commit()
        log_activity(db, None, "Admin cập nhật vai trò", f"Đã đổi vai trò tài khoản '{user.username}' thành '{role}'")
        return {"status": "success", "message": f"Đã cập nhật vai trò thành '{role}'."}

    @staticmethod
    def admin_incorrect_detections(db: Session, skip: int = 0, limit: int = 50):
        """Lấy danh sách detections bị nhận diện sai (is_correct = 0)."""
        results = (
            db.query(Prediction, Detection)
            .join(Detection, Prediction.detection_id == Detection.id)
            .filter(Prediction.is_correct == 0)
            .order_by(Prediction.verified_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [
            {
                "detection_id": pred.detection_id,
                "predicted_text": pred.predicted_text,
                "correct_plate": pred.correct_plate,
                "image_path": det.image_path,
                "source_type": det.source_type,
                "plate_confidence": det.plate_confidence,
                "verified_at": pred.verified_at.isoformat() if pred.verified_at else None,
            }
            for pred, det in results
        ]

    @staticmethod
    def admin_delete_user(user_id: int, db: Session):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
        if user.username == "abc1":
            raise HTTPException(status_code=400, detail="Không thể xóa tài khoản admin mặc định.")
        username = user.username
        db.delete(user)
        db.commit()
        log_activity(db, None, "Admin xóa tài khoản", f"Đã xóa tài khoản '{username}'")
        return {"status": "success", "message": f"Đã xóa tài khoản '{username}'."}
