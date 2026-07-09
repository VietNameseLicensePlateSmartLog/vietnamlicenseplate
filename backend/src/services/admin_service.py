from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import func as sa_func, cast, Date as SADate
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.models import models
from src.utils.helpers import log_activity, get_vietnam_now, to_naive_vn
from src.utils.security import hash_password

class AdminService:
    @staticmethod
    def admin_dashboard_stats(db: Session):
        total_users = db.query(sa_func.count(models.User.id)).scalar() or 0
        total_detections = db.query(sa_func.count(models.Detection.id)).scalar() or 0
        total_verified = db.query(sa_func.count(models.Prediction.id)).scalar() or 0
        unverified = total_detections - total_verified

        correct = db.query(sa_func.count(models.Prediction.id)).filter(models.Prediction.is_correct == 1).scalar() or 0
        incorrect = db.query(sa_func.count(models.Prediction.id)).filter(models.Prediction.is_correct == 0).scalar() or 0
        accuracy = round((correct / (correct + incorrect)) * 100, 1) if (correct + incorrect) > 0 else 0.0

        # Detections over last 7 days (giờ VN)
        seven_days_ago = to_naive_vn(get_vietnam_now() - timedelta(days=7))
        daily_rows = db.query(
            cast(models.Detection.created_at, SADate).label("day"),
            sa_func.count(models.Detection.id).label("count")
        ).filter(
            models.Detection.created_at >= seven_days_ago
        ).group_by("day").order_by("day").all()

        daily_chart = [{"date": str(row.day), "count": row.count} for row in daily_rows]

        # Source type distribution (for donut chart)
        source_rows = db.query(
            models.Detection.source_type,
            sa_func.count(models.Detection.id).label("count")
        ).group_by(models.Detection.source_type).all()
        source_chart = [{"source": row.source_type, "count": row.count} for row in source_rows]

        # Average confidence
        avg_conf = db.query(sa_func.avg(models.Detection.plate_confidence)).scalar()
        avg_confidence = round(float(avg_conf) * 100, 1) if avg_conf else 0.0

        # Top 5 detected plates
        top_plates = db.query(
            models.Detection.plate_text,
            sa_func.count(models.Detection.id).label("count")
        ).group_by(
            models.Detection.plate_text
        ).order_by(sa_func.count(models.Detection.id).desc()).limit(5).all()
        top_plates_list = [{"plate": row.plate_text, "count": row.count} for row in top_plates]

        # Confidence distribution buckets
        conf_buckets = [
            {"label": "90-100%", "min": 0.9, "max": 1.01},
            {"label": "70-90%", "min": 0.7, "max": 0.9},
            {"label": "50-70%", "min": 0.5, "max": 0.7},
            {"label": "< 50%", "min": 0.0, "max": 0.5},
        ]
        conf_dist = []
        for bucket in conf_buckets:
            cnt = db.query(sa_func.count(models.Detection.id)).filter(
                models.Detection.plate_confidence >= bucket["min"],
                models.Detection.plate_confidence < bucket["max"]
            ).scalar() or 0
            conf_dist.append({"label": bucket["label"], "count": cnt})

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
            "top_plates": top_plates_list,
            "conf_distribution": conf_dist,
        }

    @staticmethod
    def admin_list_users(db: Session):
        users = db.query(models.User).order_by(models.User.created_at.desc()).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_verified": u.is_verified,
                "is_active": u.is_active,
                "failed_attempts": u.failed_attempts,
                "created_at": str(u.created_at) if u.created_at else None
            }
            for u in users
        ]

    @staticmethod
    def admin_toggle_user_active(user_id: int, db: Session):
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
        user.is_active = not user.is_active
        db.commit()
        action = "Kích hoạt tài khoản" if user.is_active else "Vô hiệu hóa tài khoản"
        log_activity(db, None, action, f"Tài khoản '{user.username}' (ID: {user.id}) đã được {'kích hoạt lại' if user.is_active else 'chặn bởi admin'}.")
        return {
            "status": "success",
            "message": f"Tài khoản {user.username} đã được {'kích hoạt' if user.is_active else 'vô hiệu hóa'}.",
            "is_active": user.is_active
        }

    @staticmethod
    def admin_unverified_detections(skip: int, limit: int, db: Session):
        subq = db.query(models.Prediction.detection_id).subquery()
        items = db.query(models.Detection).filter(
            ~models.Detection.id.in_(db.query(subq))
        ).order_by(models.Detection.created_at.desc()).offset(skip).limit(limit).all()
        
        return [
            {
                "id": d.id,
                "plate_text": d.plate_text,
                "plate_confidence": d.plate_confidence,
                "image_path": d.image_path,
                "source_type": d.source_type,
                "created_at": str(d.created_at) if d.created_at else None
            }
            for d in items
        ]

    @staticmethod
    def admin_verify_detection(detection_id: int, correct_plate: str, is_correct: int, verified_by: int, db: Session):
        detection = db.query(models.Detection).filter(models.Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi nhận diện.")
        
        # Check if verified_by user exists in DB, otherwise use a fallback
        user_exists = db.query(models.User).filter(models.User.id == verified_by).first()
        if not user_exists:
            fallback_user = db.query(models.User).filter(models.User.role == 'admin').first() or db.query(models.User).first()
            if fallback_user:
                verified_by = fallback_user.id
            else:
                raise HTTPException(status_code=400, detail="Không có tài khoản người dùng hợp lệ trong hệ thống để thực hiện xác minh.")

        # Check if already verified by this user
        existing = db.query(models.Prediction).filter(
            models.Prediction.detection_id == detection_id,
            models.Prediction.verified_by == verified_by
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bản ghi này đã được xác minh rồi.")
        
        pred = models.Prediction(
            detection_id=detection_id,
            verified_by=verified_by,
            plate_text=correct_plate,
            predicted_text=detection.plate_text,
            is_correct=is_correct
        )
        db.add(pred)
        
        # Update daily statistics (dùng giờ VN)
        today = get_vietnam_now().date()
        stat = db.query(models.Statistic).filter(models.Statistic.stat_date == today).first()
        if not stat:
            stat = models.Statistic(stat_date=today)
            db.add(stat)
            db.flush()
        
        if is_correct == 1:
            stat.correct_count += 1
        else:
            stat.incorrect_count += 1
        stat.unverified_count = max(0, stat.unverified_count - 1)
        
        db.commit()
        verdict = "ĐÚNG" if is_correct == 1 else "SAI"
        log_activity(db, verified_by, "Xác minh biển số", f"Biển số '{detection.plate_text}' (Detection #{detection_id}) được đánh giá {verdict}. Biển đúng: '{correct_plate}'.")
        return {"status": "success", "message": "Đã xác minh kết quả nhận diện thành công."}

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
        query = db.query(models.Detection)
        
        if plate:
            query = query.filter(models.Detection.plate_text.ilike(f"%{plate}%"))
        if source_type:
            query = query.filter(models.Detection.source_type == source_type)
        if region_id is not None:
            query = query.filter(models.Detection.region_id == region_id)
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(models.Detection.created_at >= dt_from)
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(models.Detection.created_at < dt_to)
            except ValueError:
                pass
        if verified == "yes":
            subq = db.query(models.Prediction.detection_id).subquery()
            query = query.filter(models.Detection.id.in_(db.query(subq)))
        elif verified == "no":
            subq = db.query(models.Prediction.detection_id).subquery()
            query = query.filter(~models.Detection.id.in_(db.query(subq)))
        
        items = query.order_by(models.Detection.created_at.desc()).offset(skip).limit(limit).all()
        
        return [
            {
                "id": d.id,
                "plate_text": d.plate_text,
                "plate_confidence": d.plate_confidence,
                "image_path": d.image_path,
                "source_type": d.source_type,
                "region_id": d.region_id,
                "created_at": str(d.created_at) if d.created_at else None
            }
            for d in items
        ]

    @staticmethod
    def admin_regions_stats(db: Session):
        rows = db.query(
            models.Region.name,
            sa_func.count(models.Detection.id).label("count")
        ).outerjoin(
            models.Detection, models.Detection.region_id == models.Region.id
        ).group_by(models.Region.name).all()
        
        return [{"region": row.name, "count": row.count} for row in rows]

    @staticmethod
    def admin_activity_logs(skip: int, limit: int, db: Session):
        logs = db.query(models.ActivityLog).order_by(
            models.ActivityLog.created_at.desc()
        ).offset(skip).limit(limit).all()

        return [
            {
                "id": l.id,
                "user_id": l.user_id,
                "action": l.action,
                "detail": l.detail,
                "ip_address": l.ip_address,
                "created_at": str(l.created_at) if l.created_at else None
            }
            for l in logs
        ]

    @staticmethod
    def admin_create_user(username: str, email: str, password: str, role: str, db: Session):
        """Tạo tài khoản mới từ admin panel."""
        username = username.strip()
        email = email.strip().lower()

        if len(username) < 3:
            raise HTTPException(status_code=400, detail="Tên tài khoản phải có ít nhất 3 ký tự.")
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 6 ký tự.")
        if role not in ('user', 'admin'):
            raise HTTPException(status_code=400, detail="Role phải là 'user' hoặc 'admin'.")

        # Kiểm tra trùng username
        existing = db.query(models.User).filter(models.User.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Tên tài khoản đã tồn tại.")

        # Kiểm tra trùng email
        existing_email = db.query(models.User).filter(models.User.email == email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email đã được sử dụng.")

        user = models.User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_verified=1,   # Admin tạo → tự verified
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        log_activity(db, None, "Tạo tài khoản", f"Admin tạo tài khoản '{username}' (role: {role}).")
        return {
            "status": "success",
            "message": f"Đã tạo tài khoản '{username}' thành công.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active
            }
        }

    @staticmethod
    def admin_update_user_role(user_id: int, role: str, db: Session):
        """Cập nhật role của user."""
        if role not in ('user', 'admin'):
            raise HTTPException(status_code=400, detail="Role phải là 'user' hoặc 'admin'.")

        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

        old_role = user.role
        user.role = role
        db.commit()

        log_activity(db, None, "Đổi role", f"Tài khoản '{user.username}' đổi role từ '{old_role}' → '{role}'.")
        return {
            "status": "success",
            "message": f"Đã đổi role tài khoản '{user.username}' thành '{role}'.",
            "role": role
        }

    @staticmethod
    def admin_delete_user(user_id: int, db: Session):
        """Xóa user (không cho xóa admin mặc định abc1)."""
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

        # Bảo vệ: không cho xóa admin abc1
        if user.username == 'abc1':
            raise HTTPException(status_code=400, detail="Không thể xóa tài khoản admin chính.")

        username = user.username
        # Xóa các bản ghi liên quan trước (tokens, predictions có FK đến user)
        db.query(models.Token).filter(models.Token.user_id == user_id).delete()
        db.query(models.ActivityLog).filter(models.ActivityLog.user_id == user_id).update({"user_id": None})
        db.query(models.Detection).filter(models.Detection.user_id == user_id).update({"user_id": None})
        db.query(models.VideoJob).filter(models.VideoJob.user_id == user_id).update({"user_id": None})
        db.delete(user)
        db.commit()

        log_activity(db, None, "Xóa tài khoản", f"Admin đã xóa tài khoản '{username}' (ID: {user_id}).")
        return {
            "status": "success",
            "message": f"Đã xóa tài khoản '{username}' thành công."
        }
