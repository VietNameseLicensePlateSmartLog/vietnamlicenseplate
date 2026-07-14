# History Module - Data Specification

**Module:** Lich su nhan dien  
**Table:** detections (chinh), predictions (phu)

---

## 1. Query Patterns

### 1.1 History Listing

```python
# Lay lich su theo user
query = db.query(models.Detection)
if user_id is not None:
    query = query.filter(models.Detection.user_id == user_id)

results = query.order_by(models.Detection.created_at.desc())\
    .offset(skip)\
    .limit(limit)\
    .all()
```

### 1.2 History voi User Info

```python
# Lay detection voi user info (join)
results = db.query(
    models.Detection,
    models.User.username
).outerjoin(
    models.User, models.Detection.user_id == models.User.id
).order_by(
    models.Detection.created_at.desc()
).offset(skip).limit(limit).all()
```

### 1.3 History voi Region Info

```python
# Lay detection voi region info (join)
results = db.query(
    models.Detection,
    models.Region.name
).outerjoin(
    models.Region, models.Detection.region_id == models.Region.id
).order_by(
    models.Detection.created_at.desc()
).offset(skip).limit(limit).all()
```

### 1.4 History voi Prediction Info

```python
# Lay detection da xac minh
results = db.query(
    models.Detection,
    models.Prediction
).outerjoin(
    models.Prediction, models.Detection.id == models.Prediction.detection_id
).order_by(
    models.Detection.created_at.desc()
).offset(skip).limit(limit).all()
```

### 1.5 Delete Detection

```python
# Tim detection
item = db.query(models.Detection).filter(models.Detection.id == id).first()

# Xoa file anh
if item.image_path:
    local_img_path = item.image_path.lstrip('/')
    if os.path.exists(local_img_path):
        os.remove(local_img_path)

# Xoa DB
db.delete(item)
db.commit()
```

---

## 2. Filter Schemas

### 2.1 History Query Parameters

```python
# GET /history?user_id=1&skip=0&limit=20

class HistoryQuery:
    user_id: int | None = None    # Loc theo nguoi dung
    skip: int = 0                 # Phan trang: bo qua
    limit: int = 20               # Phan trang: gioi han
```

### 2.2 Admin Search Query Parameters

```python
# GET /admin/detections/search?plate=51A&source_type=camera&date_from=2026-07-01&...

class AdminSearchQuery:
    plate: str | None = None          # Tim theo bien so (ILIKE)
    source_type: str | None = None    # Loc theo nguon
    date_from: str | None = None      # Tu ngay (YYYY-MM-DD)
    date_to: str | None = None        # Den ngay (YYYY-MM-DD)
    verified: str | None = None       # "yes" / "no"
    region_id: int | None = None      # Loc theo region
    skip: int = 0
    limit: int = 20
```

---

## 3. Response Schemas

### 3.1 History Item

```json
{
  "id": "int",
  "plate_text": "string",
  "plate_confidence": "float (0.0-1.0)",
  "alt_text": "string|null",
  "alt_confidence": "float|null",
  "image_path": "string|null",
  "source_type": "camera|image|video",
  "created_at": "datetime string"
}
```

### 3.2 Delete Response

```json
{
  "status": "success",
  "message": "Da xoa thanh cong ban ghi ID=42"
}
```

### 3.3 Error Response

```json
{
  "detail": "Khong tim thay ban ghi lich su."
}
```

---

## 4. Data Relationships

### 4.1 Detection -> User

```
detections.user_id -> users.id (ON DELETE SET NULL)
```

Khi xoa user, `user_id` trong detections tro thanh NULL.

### 4.2 Detection -> Region

```
detections.region_id -> regions.id (ON DELETE SET NULL)
```

Khi xoa region, `region_id` trong detections tro thanh NULL.

### 4.3 Detection -> VideoJob

```
detections.video_job_id -> video_jobs.id (ON DELETE SET NULL)
```

Khi xoa video job, `video_job_id` trong detections tro thanh NULL.

### 4.4 Detection -> Prediction

```
predictions.detection_id -> detections.id (ON DELETE CASCADE)
```

Khi xoa detection, prediction tuong ung bi xoa theo.

---

## 5. File Cleanup

### 5.1 Snapshot Files

```
Anh snapshot duoc luu tai: backend/static/snapshots/{UUID}.jpg
Duong dan trong DB: /static/snapshots/{UUID}.jpg
```

### 5.2 Xoa khi xoa Detection

```python
if item.image_path:
    local_img_path = item.image_path.lstrip('/')
    # local_img_path = "static/snapshots/xxx.jpg"
    if os.path.exists(local_img_path):
        os.remove(local_img_path)
```

### 5.3 Xoa khi xoa Detection (Admin)

```python
if detection.image_path:
    file_path = os.path.join("backend", detection.image_path.lstrip("/"))
    # file_path = "backend/static/snapshots/xxx.jpg"
    if os.path.exists(file_path):
        os.remove(file_path)
```
