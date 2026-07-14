"""
Tự động dọn dẹp dữ liệu cũ: xóa ảnh Cloudinary + file local + bản ghi detections
sau số ngày quy định (mặc định 7 ngày).

Được gọi bởi background task trong main.py lifespan.
"""
import os
import re
from datetime import datetime, timedelta, timezone

from src.core.config.database import SessionLocal
from src.modules.detection.models import Detection, Prediction


# múi giờ UTC+7 để hiển thị log
_VN_TZ = timezone(timedelta(hours=7))

# regex trích xuất public_id từ Cloudinary URL
# URL mẫu: https://res.cloudinary.com/demo/image/upload/v123456/anpr-snapshots/abc123.jpg
#         → public_id = "anpr-snapshots/abc123"
_CLOUDINARY_URL_RE = re.compile(
    r"https?://[^/]+/[^/]+/image/upload/"   # host + /image/upload/
    r"(?:v\d+/)?"                            # optional version prefix v123456/
    r"(.+?)"                                 # public_id (non-greedy)
    r"(?:\.\w+)$"                            # file extension
)


def _extract_public_id(cloud_url: str) -> str | None:
    """Trích xuất public_id từ Cloudinary URL.

    Ví dụ:
        "https://res.cloudinary.com/demo/image/upload/v1/anpr-snapshots/abc.jpg"
        → "anpr-snapshots/abc"
    """
    if not cloud_url or "cloudinary" not in cloud_url:
        return None
    match = _CLOUDINARY_URL_RE.search(cloud_url)
    return match.group(1) if match else None


def _delete_cloudinary_images(public_ids: list[str]) -> dict[str, int]:
    """Xóa nhiều ảnh trên Cloudinary bằng public_id.

    Trả về dict {"success": n, "failed": n}.
    """
    import cloudinary.uploader

    stats = {"success": 0, "failed": 0}
    for pid in public_ids:
        try:
            result = cloudinary.uploader.destroy(pid, resource_type="image")
            if result.get("result") == "ok":
                stats["success"] += 1
            else:
                print(f"[CLEANUP] Cloudinary destroy returned: {result} for {pid}")
                stats["failed"] += 1
        except Exception as e:
            print(f"[CLEANUP] Cloudinary delete error for {pid}: {e}")
            stats["failed"] += 1
    return stats


def cleanup_old_detections(days: int = 7) -> dict:
    """Xóa detections, ảnh Cloudinary, và file local cũ hơn `days` ngày.

    Returns:
        dict với keys: deleted_db, deleted_cloud, failed_cloud, deleted_local
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    now_vn = datetime.now(_VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[CLEANUP] 🔍 Starting cleanup — older than {days} days (before {cutoff.isoformat()}) | {now_vn}")

    result = {"deleted_db": 0, "deleted_cloud": 0, "failed_cloud": 0, "deleted_local": 0}

    # ── Bước 1: Tìm detections cũ ──
    with SessionLocal() as db:
        old_detections = db.query(Detection).filter(
            Detection.created_at < cutoff,
            Detection.image_path.isnot(None),
        ).all()

        if not old_detections:
            print("[CLEANUP] ✅ No old detections found. Done.")
            return result

        # Phân loại: Cloudinary vs local
        cloud_ids_to_delete: list[str] = []
        local_paths_to_delete: list[str] = []
        detection_ids_to_delete: list[int] = []

        for det in old_detections:
            public_id = _extract_public_id(det.image_path)
            if public_id:
                cloud_ids_to_delete.append(public_id)
            elif det.image_path.startswith("/static/") or det.image_path.startswith("static/"):
                local_paths_to_delete.append(det.image_path)
            elif os.path.basename(det.image_path) and det.image_path.endswith('.jpg'):
                # Absolute path mới (từ __file__-based save) — kiểm tra tồn tại trực tiếp
                if os.path.exists(det.image_path):
                    local_paths_to_delete.append(det.image_path)
            detection_ids_to_delete.append(det.id)

        print(f"[CLEANUP] Found {len(old_detections)} old detections "
              f"({len(cloud_ids_to_delete)} Cloudinary, {len(local_paths_to_delete)} local)")

        # ── Bước 2: Xóa ảnh trên Cloudinary ──
        if cloud_ids_to_delete:
            stats = _delete_cloudinary_images(cloud_ids_to_delete)
            result["deleted_cloud"] = stats["success"]
            result["failed_cloud"] = stats["failed"]
            print(f"[CLEANUP] Cloudinary: {stats['success']} deleted, {stats['failed']} failed")

        # ── Bước 2b: Xóa file local ──
        for local_path in local_paths_to_delete:
            try:
                # Resolve đường dẫn vật lý
                if os.path.isabs(local_path) and os.path.exists(local_path):
                    abs_path = local_path
                else:
                    # Legacy path: "/static/snapshots/xxx.jpg" → resolve từ backend root
                    backend_root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
                    abs_path = os.path.normpath(os.path.join(backend_root, local_path.lstrip('/')))
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                    result["deleted_local"] += 1
            except Exception as e:
                print(f"[CLEANUP] Failed to delete local file {local_path}: {e}")

        if result["deleted_local"] > 0:
            print(f"[CLEANUP] Local files: {result['deleted_local']} deleted")

        # ── Bước 3: Xóa predictions liên quan trước ──
        if detection_ids_to_delete:
            deleted_preds = db.query(Prediction).filter(
                Prediction.detection_id.in_(detection_ids_to_delete)
            ).delete(synchronize_session=False)
            print(f"[CLEANUP] Deleted {deleted_preds} related predictions")

        # ── Bước 4: Xóa detections ──
        deleted_dets = db.query(Detection).filter(
            Detection.id.in_(detection_ids_to_delete)
        ).delete(synchronize_session=False)
        result["deleted_db"] = deleted_dets
        db.commit()

        print(f"[CLEANUP] ✅ Done — DB: {deleted_dets} detections deleted | "
              f"Cloudinary: {result['deleted_cloud']} images deleted | "
              f"Local: {result['deleted_local']} files deleted")

    return result
