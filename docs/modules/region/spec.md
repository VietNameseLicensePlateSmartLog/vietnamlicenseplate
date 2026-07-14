# Region Module - Functional Specification

**Module:** Phan vung camera  
**Route prefix:** `/api/v1`  
**Files:** `routes/regions.py`, `controllers/region_controller.py`, `services/region_service.py`

---

## 1. Region CRUD Operations

### 1.1 GET `/regions`

**Muc dich:** Lay danh sach cac phan vung camera dang hoat dong.

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "Camera Cổng Chính (Gate 1)",
    "location": "Cổng chính tòa nhà A",
    "is_active": true,
    "created_at": "2026-07-01 10:00:00"
  },
  {
    "id": 2,
    "name": "Camera Cổng Phụ (Gate 2)",
    "location": "Cổng phụ đường phía sau",
    "is_active": true,
    "created_at": "2026-07-01 10:00:00"
  },
  {
    "id": 3,
    "name": "Camera Hầm Gửi Xe A",
    "location": "Lối vào hầm A",
    "is_active": true,
    "created_at": "2026-07-01 10:00:00"
  },
  {
    "id": 4,
    "name": "Camera Hầm Gửi Xe B",
    "location": "Lối vào hầm B",
    "is_active": true,
    "created_at": "2026-07-01 10:00:00"
  }
]
```

**Logic:** Chi lay cac region co `is_active = True`:
```python
regions = db.query(Region).filter(Region.is_active == True).all()
```

### 1.2 Chi tiet tinh nang

- **Read only:** Hien tai chi ho tro GET (doc), khong ho tro POST/PUT/DELETE qua API
- **Admin seeder:** Regions duoc tao tu dong khi he thong khoi dau (lifespan event)
- **Su dung:** Khi nhan dien, user chon region de gan cho detection
- **Thong ke:** Admin co the xem statistics theo region

---

## 2. Default Regions Seeding

### 2.1 Auto-Seed

Khi he thong khoi dau (lifespan), neu bang `regions` trong, he thong tu dong tao 4 region mac dinh:

```python
# Trong main.py lifespan
with SessionLocal() as db:
    if db.query(models.Region).count() == 0:
        default_regions = [
            models.Region(
                name="Camera Cổng Chính (Gate 1)",
                location="Cổng chính tòa nhà A",
                is_active=True
            ),
            models.Region(
                name="Camera Cổng Phụ (Gate 2)",
                location="Cổng phụ đường phía sau",
                is_active=True
            ),
            models.Region(
                name="Camera Hầm Gửi Xe A",
                location="Lối vào hầm A",
                is_active=True
            ),
            models.Region(
                name="Camera Hầm Gửi Xe B",
                location="Lối vào hầm B",
                is_active=True
            ),
        ]
        db.add_all(default_regions)
        db.commit()
```

### 2.2 4 Region Mac Dinh

| ID | Ten | Vi tri |
|---|---|---|
| 1 | Camera Cổng Chính (Gate 1) | Cổng chính tòa nhà A |
| 2 | Camera Cổng Phụ (Gate 2) | Cổng phụ đường phía sau |
| 3 | Camera Hầm Gửi Xe A | Lối vào hầm A |
| 4 | Camera Hầm Gửi Xe B | Lối vào hầm B |

### 2.3 Region trong Detection Flow

Khi nhan dien (image/video/realtime):
- Frontend gui `region_id` kem voi request
- Neu `region_id` la NULL -> he thong tu dong gan region dau tien (ID=1)
- Detection duoc luu voi `region_id` tuong ung

```python
# Trong predict_service.py
if not region_id:
    first_reg = db.query(models.Region).first()
    if first_reg:
        region_id = first_reg.id
```
