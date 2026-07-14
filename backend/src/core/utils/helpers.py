import os
import uuid
from datetime import datetime, timezone, timedelta
from PIL import Image
from sqlalchemy.orm import Session

VIETNAM_TZ = timezone(timedelta(hours=7))

# ── Path constants — dùng __file__ để resolve chuẩn xác bất kể CWD ──
_BACKEND_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
_SNAPSHOTS_DIR = os.path.join(_BACKEND_ROOT, 'static', 'snapshots')

def get_vietnam_now() -> datetime:
    return datetime.now(VIETNAM_TZ)

def to_naive_vn(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(VIETNAM_TZ)
    return dt.replace(tzinfo=None)

def save_snapshot_image(annotated_img: Image.Image) -> str:
    """Lưu ảnh snapshot: upload lên Cloudinary nếu có cấu hình, nếu không thì lưu local.
    Trả về URL (Cloudinary URL hoặc local path)."""
    from src.core.config.settings import settings

    # Nếu có Cloudinary config → upload lên cloud
    if settings.CLOUDINARY_URL:
        return _upload_to_cloudinary(annotated_img)

    # Fallback: lưu local
    return _save_snapshot_local(annotated_img)


def _upload_to_cloudinary(annotated_img: Image.Image) -> str:
    """Upload ảnh lên Cloudinary. Trả về secure_url."""
    try:
        import cloudinary.uploader
        import io
        from src.core.config.settings import settings

        # Chuyển PIL Image sang bytes
        buffer = io.BytesIO()
        annotated_img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        # Upload lên Cloudinary
        result = cloudinary.uploader.upload(
            buffer,
            folder=settings.CLOUDINARY_FOLDER,
            resource_type="image",
            format="jpg",
        )
        url = result.get("secure_url", "")
        print(f"[SNAPSHOT] ✅ Uploaded to Cloudinary: {url}")
        return url

    except Exception as e:
        print(f"[SNAPSHOT] ⚠️ Cloudinary upload failed: {e} — falling back to local")
        return _save_snapshot_local(annotated_img)


def _save_snapshot_local(annotated_img: Image.Image) -> str:
    """Lưu ảnh snapshot local. Trả về local path."""
    os.makedirs(_SNAPSHOTS_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}.jpg"
    filepath = os.path.join(_SNAPSHOTS_DIR, filename)
    annotated_img.save(filepath, format="JPEG")
    return filepath


def save_snapshot_local_only(annotated_img: Image.Image) -> str:
    """Lưu ảnh snapshot local (không upload Cloudinary). Trả về local path."""
    return _save_snapshot_local(annotated_img)


def batch_upload_to_cloudinary(local_paths: list[str]) -> dict[str, str]:
    """Upload nhiều ảnh local lên Cloudinary cùng lúc.
    Trả về dict {local_path: cloud_url} cho các ảnh upload thành công.
    Ảnh upload fail sẽ bị bỏ qua (không crash)."""
    import cloudinary.uploader
    import io
    from src.core.config.settings import settings

    if not settings.CLOUDINARY_URL or not local_paths:
        return {}

    mapping = {}
    # Deduplicate paths
    unique_paths = list(set(local_paths))
    print(f"[BATCH-UPLOAD] Bat dau upload {len(unique_paths)} anh len Cloudinary...")

    for local_path in unique_paths:
        try:
            # Resolve to absolute path
            abs_path = local_path
            if not os.path.isabs(local_path):
                # Relative path → resolve from backend root
                abs_path = os.path.normpath(os.path.join(_BACKEND_ROOT, local_path.lstrip('/')))
            elif not os.path.exists(local_path) and os.path.basename(local_path) == os.path.basename(local_path):
                # Absolute path không tồn tại → thử fallback qua _BACKEND_ROOT
                # (cho legacy paths dạng /static/snapshots/xxx.jpg từ CWD-based save)
                fallback = os.path.join(_SNAPSHOTS_DIR, os.path.basename(local_path))
                if os.path.exists(fallback):
                    abs_path = fallback

            if not os.path.exists(abs_path):
                print(f"[BATCH-UPLOAD] Khong tim thay file: {abs_path} (source: {local_path})")
                continue

            result = cloudinary.uploader.upload(
                abs_path,
                folder=settings.CLOUDINARY_FOLDER,
                resource_type="image",
                format="jpg",
            )
            url = result.get("secure_url", "")
            if url:
                mapping[local_path] = url
                print(f"[BATCH-UPLOAD] OK: {local_path} -> {url}")
                # Xóa file local sau khi upload thành công
                try:
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        print(f"[BATCH-UPLOAD] Da xoa local: {abs_path}")
                except Exception as del_err:
                    print(f"[BATCH-UPLOAD] Khong the xoa local {abs_path}: {del_err}")
        except Exception as e:
            print(f"[BATCH-UPLOAD] Loi upload {local_path}: {e}")

    print(f"[BATCH-UPLOAD] Hoan thanh: {len(mapping)}/{len(unique_paths)} anh thanh cong")
    return mapping


def update_detection_paths_to_cloudinary(mapping: dict[str, str]):
    """Cập nhật image_path trong database từ local path sang Cloudinary URL."""
    if not mapping:
        return
    from src.core.config.database import engine
    from sqlalchemy import text as sql_text

    with engine.connect() as conn:
        for local_path, cloud_url in mapping.items():
            conn.execute(
                sql_text("UPDATE detections SET image_path = :cloud_url WHERE image_path = :local_path"),
                {"cloud_url": cloud_url, "local_path": local_path}
            )
        conn.commit()
    print(f"[BATCH-UPLOAD] Da cap nhat {len(mapping)} ban ghi trong database")


def cleanup_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def is_similar_plate(p1: str, p2: str) -> bool:
    clean1 = p1.replace("-", "").replace(".", "").replace(" ", "").upper()
    clean2 = p2.replace("-", "").replace(".", "").replace(" ", "").upper()
    if clean1 == clean2:
        return True
    shorter, longer = (clean1, clean2) if len(clean1) <= len(clean2) else (clean2, clean1)
    if len(shorter) == 0:
        return False
    match_count = sum(1 for i in range(len(shorter)) if shorter[i] == longer[i])
    similarity = match_count / len(shorter)
    return similarity >= 0.7

def log_activity(db: Session, user_id: int | None, action: str, detail: str = "", ip_address: str = ""):
    try:
        from src.modules.admin.models import ActivityLog
        entry = ActivityLog(
            user_id=user_id,
            action=action,
            detail=detail,
            ip_address=ip_address
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
