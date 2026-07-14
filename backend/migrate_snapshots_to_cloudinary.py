"""
Migration script: Upload ảnh snapshot local lên Cloudinary.
Chạy 1 lần duy nhất, cập nhật image_path trong database.

Cách chạy:
    cd backend
    .\venv\Scripts\python.exe migrate_snapshots_to_cloudinary.py
"""
import os
import sys
import io
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import cloudinary
import cloudinary.uploader
from sqlalchemy import create_engine, text

# ── Config ──
DATABASE_URL = os.getenv("DATABASE_URL")
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "anpr-snapshots")

if not DATABASE_URL:
    print("❌ Không tìm thấy DATABASE_URL trong .env")
    sys.exit(1)

if not CLOUDINARY_URL:
    print("❌ Không tìm thấy CLOUDINARY_URL trong .env")
    sys.exit(1)

# Cloudinary auto-config từ env
cloudinary.config(secure=True)

# ── Kết nối DB ──
engine = create_engine(DATABASE_URL)


def upload_image_to_cloudinary(local_path: str) -> str | None:
    """Upload 1 file ảnh lên Cloudinary, trả về secure_url hoặc None nếu lỗi."""
    if not os.path.exists(local_path):
        return None
    try:
        result = cloudinary.uploader.upload(
            local_path,
            folder=CLOUDINARY_FOLDER,
            resource_type="image",
            format="jpg",
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"  ⚠️  Lỗi upload {local_path}: {e}")
        return None


def main():
    with engine.connect() as conn:
        # Lấy tất cả records có image_path local
        rows = conn.execute(text(
            "SELECT id, image_path FROM detections WHERE image_path LIKE '/static/%' ORDER BY id ASC"
        )).fetchall()

        if not rows:
            print("✅ Không có ảnh local nào cần migrate.")
            return

        print(f"📦 Tìm thấy {len(rows)} records có ảnh local.\n")

        # Deduplicate: chỉ upload mỗi file 1 lần
        unique_paths = {}
        for row in rows:
            path = row.image_path
            if path not in unique_paths:
                unique_paths[path] = []
            unique_paths[path].append(row.id)

        print(f"🖼️  {len(unique_paths)} file ảnh duy nhất cần upload.\n")

        # Upload từng file
        success = 0
        failed = 0
        for local_path, record_ids in unique_paths.items():
            # Convert relative path to absolute
            abs_path = os.path.join("static", "snapshots", Path(local_path).name)
            if not os.path.exists(abs_path):
                # Thử với path tuyệt đối
                abs_path = str(Path(__file__).parent / "static" / "snapshots" / Path(local_path).name)

            print(f"⬆️  Uploading: {Path(local_path).name} (records: {record_ids})")
            cloud_url = upload_image_to_cloudinary(abs_path)

            if cloud_url:
                # Cập nhật tất cả records dùng file này
                conn.execute(text(
                    "UPDATE detections SET image_path = :url WHERE image_path = :old_path"
                ), {"url": cloud_url, "old_path": local_path})
                conn.commit()
                print(f"  ✅ → {cloud_url}")
                success += 1
            else:
                print(f"  ❌ Bỏ qua (file không tồn tại hoặc lỗi upload)")
                failed += 1

        print(f"\n{'='*50}")
        print(f"✅ Thành công: {success} file")
        print(f"❌ Lỗi/Bỏ qua: {failed} file")
        print(f"📊 Tổng records đã cập nhật: {len(rows)}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
