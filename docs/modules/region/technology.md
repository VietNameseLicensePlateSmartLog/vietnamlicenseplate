# Region Module - Technology Specification

**Module:** Phan vung camera  
**Files:** `services/region_service.py`, `routes/regions.py`, `controllers/region_controller.py`

---

## 1. Simple CRUD Operations

### 1.1 Service Layer

```python
from sqlalchemy.orm import Session
from src.models import models

class RegionService:
    @staticmethod
    def get_regions(db: Session):
        return db.query(models.Region).filter(models.Region.is_active == True).all()
```

### 1.2 Controller Layer

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.services.region_service import RegionService

class RegionController:
    @staticmethod
    def get_regions(db: Session = Depends(get_db)):
        return RegionService.get_regions(db)
```

### 1.3 Route Layer

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.region_controller import RegionController

router = APIRouter(tags=["Regions"])

@router.get("/regions")
def get_regions(db: Session = Depends(get_db)):
    return RegionController.get_regions(db)
```

---

## 2. Database Seeding

### 2.1 Implementation

Seeding duoc thuc hien trong `main.py` lifespan event:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... AI init, create tables ...

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
```

### 2.2 Condition Check

```python
# Chi seed neu bang trong
if db.query(models.Region).count() == 0:
    # Seed...
```

---

## 3. Integration voi Detection Flow

### 3.1 Image Upload

```python
# predict_service.py
async def predict_image(file, user_id, region_id, db):
    # ...
    if not region_id:
        first_reg = db.query(models.Region).first()
        if first_reg:
            region_id = first_reg.id

    db_detection = models.Detection(
        # ...
        region_id=region_id
    )
```

### 3.2 Video Upload

```python
# predict_service.py
async def predict_video(file, user_id, region_id, db):
    if not region_id:
        first_reg = db.query(models.Region).first()
        if first_reg:
            region_id = first_reg.id
    # ...
```

### 3.3 WebSocket Realtime

```python
# predict_service.py
async def handle_websocket(websocket):
    # ...
    region_id = int(data.get("region_id")) if data.get("region_id") is not None else None
    # ...
    actual_region_id = region_id
    if not actual_region_id:
        with SessionLocal() as db:
            first_reg = db.query(models.Region).first()
            if first_reg:
                actual_region_id = first_reg.id
```

---

## 4. Statistics Integration

### 4.1 Region Stats (Admin)

```python
# admin_service.py
@staticmethod
def admin_regions_stats(db: Session):
    rows = db.query(
        models.Region.name,
        sa_func.count(models.Detection.id).label("count")
    ).outerjoin(
        models.Detection, models.Detection.region_id == models.Region.id
    ).group_by(models.Region.name).all()

    return [{"region": row.name, "count": row.count} for row in rows]
```

### 4.2 Search by Region

```python
# admin_service.py
@staticmethod
def admin_search_detections(region_id=None, ...):
    query = db.query(models.Detection)
    if region_id is not None:
        query = query.filter(models.Detection.region_id == region_id)
    # ...
```

---

## 5. Database Migration Note

He thong su dung `Base.metadata.create_all()` de tao bang tu dong khi khoi dau. Khong can migration tool rieng.

```python
# main.py lifespan
Base.metadata.create_all(bind=engine)
```

Neu can them column moi, su dung soft migration voi exception handling:

```python
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
    pass  # Column da ton tai
```
