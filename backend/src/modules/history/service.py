from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.modules.detection.models import Detection

class HistoryService:
    @staticmethod
    def get_history(db: Session, user_id: int | None = None, skip: int = 0, limit: int = 50):
        query = db.query(Detection)
        if user_id:
            query = query.filter(Detection.user_id == user_id)
        detections = query.order_by(Detection.created_at.desc()).offset(skip).limit(limit).all()
        return [
            {
                "id": d.id,
                "plate_text": d.plate_text,
                "plate_confidence": d.plate_confidence,
                "alt_text": d.alt_text,
                "alt_confidence": d.alt_confidence,
                "image_path": d.image_path,
                "source_type": d.source_type,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in detections
        ]

    @staticmethod
    def delete_history(db: Session, detection_id: int):
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên nhận diện.")
        db.delete(detection)
        db.commit()
        return {"status": "success", "message": "Đã xóa phiên nhận diện."}
