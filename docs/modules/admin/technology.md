# Admin Module - Technology Specification

**Module:** Quan tri he thong  
**Files:** `services/admin_service.py`

---

## 1. SQLAlchemy Aggregate Queries

### 1.1 Import

```python
from sqlalchemy import func as sa_func, cast, Date as SADate
from sqlalchemy.orm import Session
```

### 1.2 Count Queries

```python
# Tong so
total_users = db.query(sa_func.count(models.User.id)).scalar() or 0
total_detections = db.query(sa_func.count(models.Detection.id)).scalar() or 0
total_verified = db.query(sa_func.count(models.Prediction.id)).scalar() or 0

# Dem theo dieu kien
correct = db.query(sa_func.count(models.Prediction.id)).filter(
    models.Prediction.is_correct == 1
).scalar() or 0
```

### 1.3 Average Query

```python
avg_conf = db.query(sa_func.avg(models.Detection.plate_confidence)).scalar()
avg_confidence = round(float(avg_conf) * 100, 1) if avg_conf else 0.0
```

### 1.4 Group By Queries

```python
# Group by source type
source_rows = db.query(
    models.Detection.source_type,
    sa_func.count(models.Detection.id).label("count")
).group_by(models.Detection.source_type).all()

# Group by plate text (top N)
top_plates = db.query(
    models.Detection.plate_text,
    sa_func.count(models.Detection.id).label("count")
).group_by(
    models.Detection.plate_text
).order_by(sa_func.count(models.Detection.id).desc()).limit(5).all()
```

### 1.5 Date Grouping

```python
from sqlalchemy import cast, Date as SADate

daily_rows = db.query(
    cast(models.Detection.created_at, SADate).label("day"),
    sa_func.count(models.Detection.id).label("count")
).filter(
    models.Detection.created_at >= seven_days_ago
).group_by("day").order_by("day").all()
```

### 1.6 LEFT JOIN (Regions Stats)

```python
rows = db.query(
    models.Region.name,
    sa_func.count(models.Detection.id).label("count")
).outerjoin(
    models.Detection, models.Detection.region_id == models.Region.id
).group_by(models.Region.name).all()
```

### 1.7 Subquery (Unverified Detections)

```python
subq = db.query(models.Prediction.detection_id).subquery()
items = db.query(models.Detection).filter(
    ~models.Detection.id.in_(db.query(subq))
).all()
```

### 1.8 Bucket Query (Confidence Distribution)

```python
conf_buckets = [
    {"label": "90-100%", "min": 0.9, "max": 1.01},
    {"label": "70-90%", "min": 0.7, "max": 0.9},
    {"label": "50-70%", "min": 0.5, "max": 0.7},
    {"label": "< 50%", "min": 0.0, "max": 0.5},
]

for bucket in conf_buckets:
    cnt = db.query(sa_func.count(models.Detection.id)).filter(
        models.Detection.plate_confidence >= bucket["min"],
        models.Detection.plate_confidence < bucket["max"]
    ).scalar() or 0
    conf_dist.append({"label": bucket["label"], "count": cnt})
```

---

## 2. Chart Data Formatting

### 2.1 Daily Chart (Line/Bar Chart)

```python
# Input tu DB
daily_rows = [
    (date(2026, 7, 4), 45),
    (date(2026, 7, 5), 67),
    # ...
]

# Format cho frontend
daily_chart = [{"date": str(row.day), "count": row.count} for row in daily_rows]
# Output: [{"date": "2026-07-04", "count": 45}, ...]
```

### 2.2 Source Chart (Donut/Pie Chart)

```python
source_rows = [
    ("camera", 500),
    ("image", 400),
    ("video", 334),
]

source_chart = [{"source": row.source_type, "count": row.count} for row in source_rows]
# Output: [{"source": "camera", "count": 500}, ...]
```

### 2.3 Top Plates (Horizontal Bar Chart)

```python
top_plates = [
    ("51A-12345", 25),
    ("29B1-67890", 18),
    # ...
]

top_plates_list = [{"plate": row.plate_text, "count": row.count} for row in top_plates]
# Output: [{"plate": "51A-12345", "count": 25}, ...]
```

### 2.4 Confidence Distribution (Bar Chart)

```python
conf_dist = [
    {"label": "90-100%", "count": 500},
    {"label": "70-90%", "count": 400},
    {"label": "50-70%", "count": 200},
    {"label": "< 50%", "count": 134},
]
```

### 2.5 Region Stats (Bar Chart)

```python
# Tu LEFT JOIN query
regions_stats = [
    {"region": "Camera Cổng Chính", "count": 450},
    {"region": "Camera Cổng Phụ", "count": 320},
    # ...
]
```

---

## 3. Permission Checks (Admin-Only)

### 3.1 Route-Level Protection

Hien tai he thong su dung frontend routing de bao ve admin area:
- `/admin/*` pages kiem tra role truoc khi render
- Backend khong co middleware xac thuc admin cho tung route

### 3.2 Admin Account Protection

```python
# Khong cho xoa tai khoan admin mac dinh
if user.username == 'abc1':
    raise HTTPException(status_code=400, detail="Khong the xoa tai khoan admin chinh.")
```

### 3.3 User Verification Fallback

```python
# Kiem tra verified_by user ton tai
user_exists = db.query(models.User).filter(models.User.id == verified_by).first()
if not user_exists:
    fallback_user = db.query(models.User).filter(models.User.role == 'admin').first() or db.query(models.User).first()
    if fallback_user:
        verified_by = fallback_user.id
    else:
        raise HTTPException(status_code=400, detail="Khong co tai khoan hop le.")
```

### 3.4 Delete User Cascade

```python
# Khi xoa user, xu ly cascade
db.query(models.Token).filter(models.Token.user_id == user_id).delete()
db.query(models.ActivityLog).filter(models.ActivityLog.user_id == user_id).update({"user_id": None})
db.query(models.Detection).filter(models.Detection.user_id == user_id).update({"user_id": None})
db.query(models.VideoJob).filter(models.VideoJob.user_id == user_id).update({"user_id": None})
db.delete(user)
db.commit()
```

### 3.5 Delete Detection Cascade

```python
# Khi xoa detection, xu ly prediction va statistic
if detection.image_path:
    file_path = os.path.join("backend", detection.image_path.lstrip("/"))
    if os.path.exists(file_path):
        os.remove(file_path)

prediction = db.query(models.Prediction).filter(models.Prediction.detection_id == detection_id).first()
if prediction:
    # Cap nhat statistic
    if prediction.is_correct == 1:
        stat.correct_count = max(0, stat.correct_count - 1)
    else:
        stat.incorrect_count = max(0, stat.incorrect_count - 1)
    db.delete(prediction)

db.delete(detection)
db.commit()
```

---

## 4. Mui gio Viet Nam (UTC+7)

### 4.1 Configuration

```python
from datetime import datetime, timezone, timedelta

VIETNAM_TZ = timezone(timedelta(hours=7))

def get_vietnam_now():
    return datetime.now(VIETNAM_TZ)

def to_naive_vn(dt):
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(VIETNAM_TZ)
    return dt.replace(tzinfo=None)
```

### 4.2 Su dung trong Admin

```python
# Daily stats dung mui gio VN
today = get_vietnam_now().date()
stat = db.query(models.Statistic).filter(models.Statistic.stat_date == today).first()

# 7 ngay gan nhat
seven_days_ago = to_naive_vn(get_vietnam_now() - timedelta(days=7))
```

---

## 5. Format Confidence Values

### 5.1 DB Storage

Confidence duoc luu trong DB gia tri `0.0 - 1.0` (khong nhan 100).

### 5.2 Display

Frontend nhan gia tri `0.0 - 1.0` tu API va nhan 100 khi hien thi:
```typescript
// Frontend
const confidence = (plate_confidence * 100).toFixed(2) + "%";
// VD: 0.92 -> "92.00%"
```

### 5.3 Average Confidence

```python
avg_conf = db.query(sa_func.avg(models.Detection.plate_confidence)).scalar()
avg_confidence = round(float(avg_conf) * 100, 1)  # Chuyen thanh percentage
# VD: 0.875 -> 87.5
```
