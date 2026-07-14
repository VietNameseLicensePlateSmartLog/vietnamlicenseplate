# Admin Module - Data Specification

**Module:** Quan tri he thong  
**Tables:** activity_logs, statistics

---

## 1. ActivityLog Table Schema

```sql
CREATE TABLE activity_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(50) NOT NULL,
    detail      TEXT,
    ip_address  VARCHAR(45),
    created_at  TIMESTAMP DEFAULT NOW()
);
```

### 1.1 Field Definitions

| Field | Kieu du lieu | Mo ta |
|---|---|---|
| `id` | INTEGER (PK) | ID tu tang |
| `user_id` | INTEGER (FK -> users) | Nguoi thuc hien (NULL neu he thong hoac admin) |
| `action` | VARCHAR(50) | Ten hanh dong |
| `detail` | TEXT | Mo ta chi tiet |
| `ip_address` | VARCHAR(45) | Dia chi IP (toi da 45 ky tu cho IPv6) |
| `created_at` | TIMESTAMP | Thoi gian tao (auto) |

### 1.2 Indexes

- `ix_activity_logs_id` (PRIMARY KEY)

### 1.3 Relationship

```python
class ActivityLog(Base):
    __tablename__ = "activity_logs"
    # ...
    user = relationship("User", foreign_keys=[user_id], lazy="select")
```

### 1.4 Action Types

| Action | Mo ta | Vi du detail |
|---|---|---|
| Dang ky | Tai khoan moi duoc tao | "Tai khoan 'user1' da dang ky voi email user@gmail.com." |
| Dang nhap | Dang nhap thanh cong | "Tai khoan 'user1' dang nhap thanh cong (role: user)." |
| Dang nhap that bai | Sai mat khau/vo hieu hoa | "Tai khoan 'user1' nhap sai mat khau." |
| Dang xuat | Dang xuat | "Tai khoan 'user1' dang xuat thanh cong." |
| Tai len video | Upload video | "Khoi chay xu ly video 'clip.mp4' (Job #5)." |
| Xac minh bien so | Admin verify | "Bien so '51A-12345' (Detection #42) duoc danh gia DUNG." |
| Tao tai khoan | Admin tao user | "Admin tao tai khoan 'user2' (role: user)." |
| Doi role | Admin doi role | "Tai khoan 'user1' doi role tu 'user' → 'admin'." |
| Kich hoat | Admin active | "Tai khoan 'user1' da duoc kich hoat lai." |
| Vô hieu hoa | Admin block | "Tai khoan 'user1' da duoc chan boi admin." |
| Xoa tai khoan | Admin delete | "Admin da xoa tai khoan 'user1' (ID: 3)." |
| Xoa detection | Xoa detection | "Da xoa ban ghi nhan dien #42 (biển so '51A-12345')." |

### 1.5 Implementation

```python
def log_activity(db: Session, user_id: int | None, action: str, detail: str = "", ip_address: str = ""):
    try:
        entry = models.ActivityLog(
            user_id=user_id,
            action=action,
            detail=detail,
            ip_address=ip_address
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
```

---

## 2. Statistics Aggregation Queries

### 2.1 Total Counts

```python
# Tong so nguoi dung
total_users = db.query(func.count(User.id)).scalar() or 0

# Tong so detections
total_detections = db.query(func.count(Detection.id)).scalar() or 0

# Tong so da xac minh
total_verified = db.query(func.count(Prediction.id)).scalar() or 0

# Chua xac minh
unverified = total_detections - total_verified
```

### 2.2 Accuracy Calculation

```python
correct = db.query(func.count(Prediction.id)).filter(Prediction.is_correct == 1).scalar() or 0
incorrect = db.query(func.count(Prediction.id)).filter(Prediction.is_correct == 0).scalar() or 0
accuracy = round((correct / (correct + incorrect)) * 100, 1) if (correct + incorrect) > 0 else 0.0
```

### 2.3 Daily Chart (7 ngay gan nhat)

```python
seven_days_ago = to_naive_vn(get_vietnam_now() - timedelta(days=7))
daily_rows = db.query(
    cast(Detection.created_at, SADate).label("day"),
    func.count(Detection.id).label("count")
).filter(
    Detection.created_at >= seven_days_ago
).group_by("day").order_by("day").all()

daily_chart = [{"date": str(row.day), "count": row.count} for row in daily_rows]
```

### 2.4 Source Distribution

```python
source_rows = db.query(
    Detection.source_type,
    func.count(Detection.id).label("count")
).group_by(Detection.source_type).all()

source_chart = [{"source": row.source_type, "count": row.count} for row in source_rows]
```

### 2.5 Average Confidence

```python
avg_conf = db.query(func.avg(Detection.plate_confidence)).scalar()
avg_confidence = round(float(avg_conf) * 100, 1) if avg_conf else 0.0
```

### 2.6 Top 5 Plates

```python
top_plates = db.query(
    Detection.plate_text,
    func.count(Detection.id).label("count")
).group_by(
    Detection.plate_text
).order_by(func.count(Detection.id).desc()).limit(5).all()

top_plates_list = [{"plate": row.plate_text, "count": row.count} for row in top_plates]
```

### 2.7 Confidence Distribution

```python
conf_buckets = [
    {"label": "90-100%", "min": 0.9, "max": 1.01},
    {"label": "70-90%", "min": 0.7, "max": 0.9},
    {"label": "50-70%", "min": 0.5, "max": 0.7},
    {"label": "< 50%", "min": 0.0, "max": 0.5},
]

conf_dist = []
for bucket in conf_buckets:
    cnt = db.query(func.count(Detection.id)).filter(
        Detection.plate_confidence >= bucket["min"],
        Detection.plate_confidence < bucket["max"]
    ).scalar() or 0
    conf_dist.append({"label": bucket["label"], "count": cnt})
```

### 2.8 Regions Stats

```python
rows = db.query(
    Region.name,
    func.count(Detection.id).label("count")
).outerjoin(
    Detection, Detection.region_id == Region.id
).group_by(Region.name).all()

return [{"region": row.name, "count": row.count} for row in rows]
```

### 2.9 Unverified Detections

```python
subq = db.query(Prediction.detection_id).subquery()
items = db.query(Detection).filter(
    ~Detection.id.in_(db.query(subq))
).order_by(Detection.created_at.desc()).offset(skip).limit(limit).all()
```

### 2.10 Search with Filters

```python
query = db.query(Detection)

if plate:
    query = query.filter(Detection.plate_text.ilike(f"%{plate}%"))
if source_type:
    query = query.filter(Detection.source_type == source_type)
if region_id is not None:
    query = query.filter(Detection.region_id == region_id)
if date_from:
    dt_from = datetime.strptime(date_from, "%Y-%m-%d")
    query = query.filter(Detection.created_at >= dt_from)
if date_to:
    dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
    query = query.filter(Detection.created_at < dt_to)
if verified == "yes":
    subq = db.query(Prediction.detection_id).subquery()
    query = query.filter(Detection.id.in_(db.query(subq)))
elif verified == "no":
    subq = db.query(Prediction.detection_id).subquery()
    query = query.filter(~Detection.id.in_(db.query(subq)))

items = query.order_by(Detection.created_at.desc()).offset(skip).limit(limit).all()
```

---

## 3. Response Schemas for Dashboard

### 3.1 Dashboard Stats

```json
{
  "total_users": "int",
  "total_detections": "int",
  "total_verified": "int",
  "unverified": "int",
  "correct": "int",
  "incorrect": "int",
  "accuracy": "float (percentage)",
  "avg_confidence": "float (percentage)",
  "daily_chart": [
    { "date": "YYYY-MM-DD", "count": "int" }
  ],
  "source_chart": [
    { "source": "camera|image|video", "count": "int" }
  ],
  "top_plates": [
    { "plate": "string", "count": "int" }
  ],
  "conf_distribution": [
    { "label": "string", "count": "int" }
  ]
}
```

### 3.2 User List Item

```json
{
  "id": "int",
  "username": "string",
  "email": "string",
  "full_name": "string|null",
  "role": "user|admin",
  "is_verified": "0|1",
  "is_active": "bool",
  "failed_attempts": "int",
  "created_at": "datetime string"
}
```

### 3.3 Unverified Detection Item

```json
{
  "id": "int",
  "plate_text": "string",
  "plate_confidence": "float",
  "image_path": "string|null",
  "source_type": "camera|image|video",
  "created_at": "datetime string"
}
```

### 3.4 Activity Log Item

```json
{
  "id": "int",
  "user_email": "string|null",
  "action": "string",
  "detail": "string|null",
  "ip_address": "string|null",
  "created_at": "datetime string"
}
```

### 3.5 Region Stats Item

```json
{
  "region": "string",
  "count": "int"
}
```

### 3.6 Search Result Item

```json
{
  "id": "int",
  "plate_text": "string",
  "plate_confidence": "float",
  "image_path": "string|null",
  "source_type": "string",
  "region_id": "int|null",
  "created_at": "datetime string"
}
```
