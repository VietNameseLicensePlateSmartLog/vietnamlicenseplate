# Region Module - Data Specification

**Module:** Phan vung camera  
**Table:** regions

---

## 1. Region Table Schema

```sql
CREATE TABLE regions (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    location    VARCHAR(200),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 1.1 Field Definitions

| Field | Kieu du lieu | Mo ta | Rang buoc |
|---|---|---|---|
| `id` | INTEGER (PK) | ID tu tang | BAT BUOC, auto |
| `name` | VARCHAR(100) | Ten phan vung camera | BAT BUOC |
| `location` | VARCHAR(200) | Mo ta vi tri | Tu chon |
| `is_active` | BOOLEAN | Trang thai hoat dong | BAT BUOC, mac dinh TRUE |
| `created_at` | TIMESTAMP | Thoi gian tao | Auto |

### 1.2 Indexes

- `ix_regions_id` (PRIMARY KEY)

### 1.3 Relationship

- `Region` 1:N `Detection` (qua `detections.region_id`)

```python
class Region(Base):
    __tablename__ = "regions"
    # ...
    # Khong co relationship reverse, su dung truc tiep trong queries
```

---

## 2. Sample Data

| ID | Name | Location | Is Active |
|---|---|---|---|
| 1 | Camera Cổng Chính (Gate 1) | Cổng chính tòa nhà A | TRUE |
| 2 | Camera Cổng Phụ (Gate 2) | Cổng phụ đường phía sau | TRUE |
| 3 | Camera Hầm Gửi Xe A | Lối vào hầm A | TRUE |
| 4 | Camera Hầm Gửi Xe B | Lối vào hầm B | TRUE |

---

## 3. Request/Response Schemas

### 3.1 Region Response

```json
{
  "id": 1,
  "name": "Camera Cổng Chính (Gate 1)",
  "location": "Cổng chính tòa nhà A",
  "is_active": true,
  "created_at": "2026-07-01 10:00:00"
}
```

### 3.2 Region trong Detection Request

```json
{
  "file": "(multipart)",
  "user_id": 1,
  "region_id": 1
}
```

### 3.3 Region trong Detection Response

```json
{
  "id": 42,
  "plate_text": "51A-12345",
  "region_id": 1,
  "source_type": "camera",
  "created_at": "2026-07-10 14:30:00"
}
```

---

## 4. Default Region Fallback

Khi user khong chon region (region_id = NULL), he thong tu dong gan region dau tien:

```python
# Logic fallback
if not region_id:
    first_reg = db.query(models.Region).first()
    if first_reg:
        region_id = first_reg.id
# region_id = 1 (Camera Cổng Chính)
```

### 4.1 Vi du su dung

| Nguon | Fallback |
|---|---|
| Image upload (khong chon region) | region_id = 1 |
| Video upload (khong chon region) | region_id = 1 |
| WebSocket realtime (khong gui region_id) | region_id = 1 |
