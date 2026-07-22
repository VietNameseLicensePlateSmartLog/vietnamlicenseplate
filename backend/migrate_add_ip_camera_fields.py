"""Migration script — thêm IP camera connection fields vào bảng cameras.

Chạy 1 lần:
    cd backend
    python migrate_add_ip_camera_fields.py

Yêu cầu: database phải đã có bảng cameras từ trước.
"""
import sys
import os

# Thêm src vào path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from sqlalchemy import text
from src.core.config.database import engine


COLUMNS_TO_ADD = [
    ("stream_type", "VARCHAR(20) DEFAULT 'rtsp'"),
    ("username", "VARCHAR(100)"),
    ("password_encrypted", "VARCHAR(200)"),
    ("connect_timeout", "INTEGER DEFAULT 10"),
    ("reconnect_interval", "INTEGER DEFAULT 5"),
    ("max_reconnect_attempts", "INTEGER DEFAULT 10"),
    ("last_connected_at", "TIMESTAMP"),
    ("last_error", "TEXT"),
]


def column_exists(conn, table_name: str, column_name: str) -> bool:
    """Kiểm tra column có tồn tại trong table không."""
    result = conn.execute(text(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name = '{table_name}' AND column_name = '{column_name}'"
    ))
    return result.fetchone() is not None


def migrate():
    """Thêm các column mới vào bảng cameras."""
    with engine.connect() as conn:
        print("=== Migration: Add IP Camera Connection Fields ===")
        added = 0

        for col_name, col_def in COLUMNS_TO_ADD:
            if column_exists(conn, "cameras", col_name):
                print(f"  [SKIP] Column '{col_name}' đã tồn tại.")
            else:
                sql = text(f"ALTER TABLE cameras ADD COLUMN {col_name} {col_def}")
                conn.execute(sql)
                conn.commit()
                print(f"  [ADD] Column '{col_name}' — {col_def}")
                added += 1

        # Update existing cameras to have stream_type = 'rtsp'
        conn.execute(text("UPDATE cameras SET stream_type = 'rtsp' WHERE stream_type IS NULL"))
        conn.commit()

        print(f"\nDone! Đã thêm {added} columns mới.")
        print("Bảng cameras hiện có thêm fields:")
        for col_name, _ in COLUMNS_TO_ADD:
            print(f"  - {col_name}")


if __name__ == "__main__":
    migrate()
