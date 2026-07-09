import os
import uuid
from datetime import datetime, timezone, timedelta
from PIL import Image
from sqlalchemy.orm import Session
from src.models import models

# múi giờ Việt Nam UTC+7
VIETNAM_TZ = timezone(timedelta(hours=7))

def get_vietnam_now() -> datetime:
    """Trả về thời gian hiện tại theo múi giờ Việt Nam (UTC+7), có timezone info."""
    return datetime.now(VIETNAM_TZ)

def to_naive_vn(dt: datetime) -> datetime:
    """Chuyển datetime timezone-aware sang naive theo giờ VN (để so sánh với DB)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(VIETNAM_TZ)
    return dt.replace(tzinfo=None)

def save_snapshot_image(annotated_img: Image.Image) -> str:
    """Lưu ảnh snapshot vẽ bbox của biển số vào thư mục static và trả về URL tương đối."""
    os.makedirs("static/snapshots", exist_ok=True)
    filename = f"{uuid.uuid4()}.jpg"
    filepath = os.path.join("static", "snapshots", filename)
    annotated_img.save(filepath, format="JPEG")
    return f"/static/snapshots/{filename}"

def cleanup_file(path: str):
    """Hàm dọn dẹp file tạm sau khi đã gửi phản hồi cho client."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def is_similar_plate(p1: str, p2: str) -> bool:
    """So sánh 2 biển số bằng tỷ lệ ký tự giống nhau (similarity ratio).
    Nếu >= 70% ký tự ở cùng vị trí giống nhau → coi là cùng biển số."""
    clean1 = p1.replace("-", "").replace(".", "").replace(" ", "").upper()
    clean2 = p2.replace("-", "").replace(".", "").replace(" ", "").upper()

    if clean1 == clean2:
        return True

    # Lấy chuỗi ngắn hơn làm chuẩn đếm ký tự giống
    shorter, longer = (clean1, clean2) if len(clean1) <= len(clean2) else (clean2, clean1)

    if len(shorter) == 0:
        return False

    # Đếm ký tự giống nhau ở cùng vị trí (so với chuỗi ngắn hơn)
    match_count = sum(1 for i in range(len(shorter)) if shorter[i] == longer[i])

    similarity = match_count / len(shorter)
    return similarity >= 0.7

def log_activity(db: Session, user_id: int | None, action: str, detail: str = "", ip_address: str = ""):
    """Ghi một dòng nhật ký hoạt động vào cơ sở dữ liệu."""
    try:
        entry = models.ActivityLog(
            user_id=user_id,
            action=action,
            detail=detail,
            ip_address=ip_address
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
