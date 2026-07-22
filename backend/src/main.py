import os
import asyncio
import logging
import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# ── Logging configuration — must be set before any other imports that use logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Suppress noisy third-party loggers
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("starlette.websockets").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("ultralytics").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

from src.core.config.settings import settings
from src.core.config.database import engine, Base, SessionLocal
from src.core.utils.security import hash_password
from src.modules.auth.models import User
from src.modules.region.models import Region
from src.modules.detection.models import Detection, Prediction, VideoJob, Statistics
from src.modules.admin.models import ActivityLog
from src.modules.camera.models import Camera
from src.modules.detection.ai.pipeline import init_lpr_service
from src.modules.auth import router as auth_router
from src.modules.detection import router as predict_router
from src.modules.admin import router as admin_router
from src.modules.region import router as regions_router
from src.modules.history import router as history_router
from src.modules.camera import router as camera_router

# ── Auto-cleanup constants ──
CLEANUP_INTERVAL_HOURS = 24
CLEANUP_RETENTION_DAYS = 7


async def _schedule_cleanup():
    """Background task: chạy cleanup mỗi CLEANUP_INTERVAL_HOURS."""
    from src.core.utils.cleanup import cleanup_old_detections

    await asyncio.sleep(60)
    logger.info("Cleanup scheduler started — will run every %dh, retention %d days",
                CLEANUP_INTERVAL_HOURS, CLEANUP_RETENTION_DAYS)

    while True:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, cleanup_old_detections, CLEANUP_RETENTION_DAYS
            )
        except Exception as e:
            logger.error("Scheduled cleanup error: %s", e)

        await asyncio.sleep(CLEANUP_INTERVAL_HOURS * 3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    import os

    # Khởi tạo mô hình AI khi khởi chạy app
    init_lpr_service()

    # ── Tạo bảng nếu chưa tồn tại (first run) ──
    Base.metadata.create_all(bind=engine)
    logger.info("Da kiem tra/ta tat ca bang.")

    # ── Auto-migration: thêm cột mới vào bảng đã tồn tại ──
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS stream_url VARCHAR(500)"
            ))
            conn.execute(text(
                "ALTER TABLE detections ADD COLUMN IF NOT EXISTS camera_id INTEGER"
            ))
            # IP Camera connection fields
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS stream_type VARCHAR(20) DEFAULT 'rtsp'"
            ))
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS username VARCHAR(100)"
            ))
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS password_encrypted VARCHAR(200)"
            ))
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS connect_timeout INTEGER DEFAULT 10"
            ))
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS reconnect_interval INTEGER DEFAULT 5"
            ))
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS max_reconnect_attempts INTEGER DEFAULT 10"
            ))
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS last_connected_at TIMESTAMP"
            ))
            conn.execute(text(
                "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS last_error TEXT"
            ))
            conn.commit()
            logger.info("Auto-migration: camera IP connection fields added (if not exist).")
        except Exception as e:
            logger.warning("Migration skip: %s", e)

    # ── Reset database (chỉ khi RESET_DB=1 trong env) ──
    if os.getenv("RESET_DB") == "1":
        try:
            from sqlalchemy import text
            logger.info("Dang xoa toan bo database...")
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                ))
                tables = [row[0] for row in result]
                if tables:
                    truncate_sql = f"TRUNCATE TABLE {', '.join(tables)} CASCADE"
                    conn.execute(text(truncate_sql))
                    conn.commit()
                    logger.info("Da xoa du lieu %d bang: %s", len(tables), ', '.join(tables))
                else:
                    logger.info("Database trong, khong can xoa.")
        except Exception as e:
            logger.warning("Loi reset database: %s", e)

    # ── Seed regions mặc định ──
    with SessionLocal() as db:
        existing_regions = db.query(Region).count()
        if existing_regions == 0:
            default_regions = [
                Region(name="Camera Cổng Chính", location="Cổng chính tòa nhà A", is_active=True),
                Region(name="Camera Cổng Phụ", location="Cổng phụ đường phía sau", is_active=True),
                Region(name="Camera Hầm Gửi Xe A", location="Lối vào hầm A", is_active=True),
                Region(name="Camera Hầm Gửi Xe B", location="Lối vào hầm B", is_active=True),
            ]
            db.add_all(default_regions)
            db.commit()
            logger.info("Da tao 4 regions mac dinh.")
        else:
            logger.info("Da co %d regions, bo qua seed.", existing_regions)

    # ── Seed admin account: viet / 123456 ──
    with SessionLocal() as db:
        existing_admin = db.query(User).filter(User.username == 'viet').first()
        if not existing_admin:
            admin_user = User(
                username='viet',
                email='vietc3k49@gmail.com',
                password_hash=hash_password('123456'),
                full_name='Viet Admin',
                role='admin',
                is_verified=1,
                is_active=True,
                failed_attempts=0
            )
            db.add(admin_user)
            db.commit()
            logger.info("Da tao tai khoan admin: viet / 123456")
        else:
            logger.info("Tai khoan admin viet da ton tai.")

    # ── Seed cameras mặc định ──
    with SessionLocal() as db:
        existing_cameras = db.query(Camera).count()
        if existing_cameras == 0:
            regions = db.query(Region).all()
            region_map = {r.name: r.id for r in regions}

            default_cameras = [
                Camera(
                    name="Cam Cổng Chính",
                    rtsp_url="",
                    stream_type="rtsp",
                    region_id=region_map.get("Camera Cổng Chính"),
                    is_active=False,
                    fps_target=10,
                    connect_timeout=10,
                    reconnect_interval=5,
                    max_reconnect_attempts=10,
                    description="Camera giám sát cổng chính tòa nhà",
                ),
                Camera(
                    name="Cam Cổng Phụ",
                    rtsp_url="",
                    stream_type="rtsp",
                    region_id=region_map.get("Camera Cổng Phụ"),
                    is_active=False,
                    fps_target=10,
                    connect_timeout=10,
                    reconnect_interval=5,
                    max_reconnect_attempts=10,
                    description="Camera giám sát cổng phụ",
                ),
                Camera(
                    name="Cam Hầm Gửi Xe A",
                    rtsp_url="",
                    stream_type="rtsp",
                    region_id=region_map.get("Camera Hầm Gửi Xe A"),
                    is_active=False,
                    fps_target=10,
                    connect_timeout=10,
                    reconnect_interval=5,
                    max_reconnect_attempts=10,
                    description="Camera giám sát lối vào hầm A",
                ),
                Camera(
                    name="Cam Hầm Gửi Xe B",
                    rtsp_url="",
                    stream_type="rtsp",
                    region_id=region_map.get("Camera Hầm Gửi Xe B"),
                    is_active=False,
                    fps_target=10,
                    connect_timeout=10,
                    reconnect_interval=5,
                    max_reconnect_attempts=10,
                    description="Camera giám sát lối vào hầm B",
                ),
            ]
            db.add_all(default_cameras)
            db.commit()
            logger.info("Da tao 4 cameras mac dinh (tat ca tat).")
        else:
            logger.info("Da co %d cameras, bo qua seed.", existing_cameras)

    # ── Khởi động background cleanup task ──
    cleanup_task = asyncio.create_task(_schedule_cleanup())

    yield

    # ── Shutdown: hủy cleanup task ──
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Cleanup scheduler stopped.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API nhận diện biển số xe Việt Nam tích hợp PostgreSQL & YOLOv8 (Kiến trúc MVC)",
    lifespan=lifespan
)

# Cấu hình CORS để Frontend kết nối
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thư mục static phục vụ lưu và tải ảnh snapshot
# Dùng __file__ để resolve chuẩn xác bất kể CWD
_static_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static'))
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Tạo router cha với prefix /api/v1
api_router = APIRouter(prefix=settings.API_V1_STR)

# Tích hợp các sub-routers vào router cha
api_router.include_router(auth_router)
api_router.include_router(predict_router)
api_router.include_router(admin_router)
api_router.include_router(regions_router)
api_router.include_router(history_router)
api_router.include_router(camera_router)

# Đưa router cha vào FastAPI app
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
