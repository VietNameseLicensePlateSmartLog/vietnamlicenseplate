# Kết nối PostgreSQL sử dụng SQLAlchemy
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config.settings import settings

# Khởi tạo engine kết nối
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)

# Đặt timezone session = Asia/Ho_Chi_Minh (UTC+7) cho mỗi kết nối mới
# → NOW(), CURRENT_DATE trong PostgreSQL sẽ trả giờ VN
@event.listens_for(engine, "connect")
def set_pg_timezone(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET timezone TO 'Asia/Ho_Chi_Minh'")
    cursor.close()

# Khởi tạo session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Định nghĩa Base class cho các Model
Base = declarative_base()

# Helper dependency để lấy DB Session trong API routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
