import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from src.config.settings import settings
from src.config.database import engine, Base, SessionLocal
from src.models import models
from src.services.ai_pipeline import init_lpr_service
from src.utils.security import hash_password
from src.routes import (
    auth_router,
    predict_router,
    admin_router,
    regions_router,
    history_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo mô hình AI khi khởi chạy app
    init_lpr_service()

    # Tạo các bảng cơ sở dữ liệu nếu chưa có
    Base.metadata.create_all(bind=engine)

    # Thêm cột current_frame vào video_jobs nếu chưa có (migration nhẹ cho PostgreSQL)
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text(
                "DO $$ BEGIN "
                "ALTER TABLE video_jobs ADD COLUMN current_frame INTEGER DEFAULT 0; "
                "EXCEPTION WHEN duplicate_column THEN NULL; END $$"
            ))
            conn.commit()
    except Exception:
        pass  # Cột đã tồn tại

    # Seed default regions if empty
    with SessionLocal() as db:
        if db.query(models.Region).count() == 0:
            default_regions = [
                models.Region(name="Camera Cổng Chính (Gate 1)", location="Cổng chính tòa nhà A", is_active=True),
                models.Region(name="Camera Cổng Phụ (Gate 2)", location="Cổng phụ đường phía sau", is_active=True),
                models.Region(name="Camera Hầm Gửi Xe A", location="Lối vào hầm A", is_active=True),
                models.Region(name="Camera Hầm Gửi Xe B", location="Lối vào hầm B", is_active=True),
            ]
            db.add_all(default_regions)
            db.commit()

    # Seed admin account: abc1 / 123456
    with SessionLocal() as db:
        admin_user = db.query(models.User).filter(models.User.username == 'abc1').first()
        if not admin_user:
            admin_user = models.User(
                username='abc1',
                email='admin@lpr.vn',
                password_hash=hash_password('123456'),
                full_name='Admin',
                role='admin',
                is_verified=1,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("[SEED] ✅ Đã tạo tài khoản admin: abc1 / 123456")
        else:
            # Nếu tồn tại nhưng chưa phải admin → upgrade role
            if admin_user.role != 'admin':
                admin_user.role = 'admin'
                admin_user.is_verified = 1
                admin_user.password_hash = hash_password('123456')
                db.commit()
                print("[SEED] ✅ Đã upgrade abc1 thành admin (role + password reset)")
            else:
                print("[SEED] ℹ️  Tài khoản admin abc1 đã tồn tại.")

    yield

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
app.mount("/static", StaticFiles(directory="static"), name="static")

# Tạo router cha với prefix /api/v1
api_router = APIRouter(prefix=settings.API_V1_STR)

# Tích hợp các sub-routers vào router cha
api_router.include_router(auth_router)
api_router.include_router(predict_router)
api_router.include_router(admin_router)
api_router.include_router(regions_router)
api_router.include_router(history_router)

# Đưa router cha vào FastAPI app
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
