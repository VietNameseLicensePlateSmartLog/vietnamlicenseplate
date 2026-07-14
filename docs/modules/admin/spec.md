# Admin Module - Functional Specification

**Module:** Quan tri he thong  
**Route prefix:** `/api/v1/admin`  
**Files:** `routes/admin.py`, `controllers/admin_controller.py`, `services/admin_service.py`

---

## 1. Dashboard Stats Endpoints

### 1.1 GET `/admin/stats`

**Muc dich:** Lay thong ke tong quan cho dashboard admin.

**Response (200):**
```json
{
  "total_users": 5,
  "total_detections": 1234,
  "total_verified": 800,
  "unverified": 434,
  "correct": 750,
  "incorrect": 50,
  "accuracy": 93.8,
  "avg_confidence": 87.5,
  "daily_chart": [
    { "date": "2026-07-04", "count": 45 },
    { "date": "2026-07-05", "count": 67 },
    { "date": "2026-07-06", "count": 89 },
    { "date": "2026-07-07", "count": 123 },
    { "date": "2026-07-08", "count": 98 },
    { "date": "2026-07-09", "count": 156 },
    { "date": "2026-07-10", "count": 201 }
  ],
  "source_chart": [
    { "source": "camera", "count": 500 },
    { "source": "image", "count": 400 },
    { "source": "video", "count": 334 }
  ],
  "top_plates": [
    { "plate": "51A-12345", "count": 25 },
    { "plate": "29B1-67890", "count": 18 },
    { "plate": "16F7-4438", "count": 12 }
  ],
  "conf_distribution": [
    { "label": "90-100%", "count": 500 },
    { "label": "70-90%", "count": 400 },
    { "label": "50-70%", "count": 200 },
    { "label": "< 50%", "count": 134 }
  ]
}
```

**Chi tiet thong ke:**
- `total_users`: Tong so nguoi dung
- `total_detections`: Tong so luot nhan dien
- `total_verified`: So luot da xac minh
- `unverified`: So luot chua xac minh (total - verified)
- `correct`: So luot xac minh dung
- `incorrect`: So luot xac minh sai
- `accuracy`: Ti le dung (correct / (correct + incorrect) * 100)
- `avg_confidence`: Confidence trung binh (dung Detection.plate_confidence)
- `daily_chart`: Bieu do nhan dien theo ngay (7 ngay gan nhat)
- `source_chart`: Bieu do theo loai nguon (camera/image/video)
- `top_plates`: Top 5 bien so phat hien nhieu nhat
- `conf_distribution`: Phan bo confidence (4 bucket)

---

## 2. User Management CRUD

### 2.1 GET `/admin/users`

**Muc dich:** Lay danh sach tat ca nguoi dung.

**Response (200):**
```json
[
  {
    "id": 1,
    "username": "abc1",
    "email": "admin@lpr.vn",
    "full_name": "Admin",
    "role": "admin",
    "is_verified": 1,
    "is_active": true,
    "failed_attempts": 0,
    "created_at": "2026-07-01 10:00:00"
  },
  {
    "id": 2,
    "username": "nguoidung",
    "email": "user@gmail.com",
    "full_name": null,
    "role": "user",
    "is_verified": 1,
    "is_active": true,
    "failed_attempts": 0,
    "created_at": "2026-07-05 14:30:00"
  }
]
```

### 2.2 POST `/admin/users`

**Muc dich:** Tao tai khoan moi tu admin panel.

**Request Body:**
```json
{
  "username": "user2",
  "email": "user2@gmail.com",
  "password": "123456",
  "role": "user"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Da tao tai khoan 'user2' thanh cong.",
  "user": {
    "id": 3,
    "username": "user2",
    "email": "user2@gmail.com",
    "role": "user",
    "is_active": true
  }
}
```

**Quy tac:**
- Username toi thieu 3 ky tu
- Password toi thieu 6 ky tu
- Role chi duoc la 'user' hoac 'admin'
- Tai khoan admin tao tu dong `is_verified=1` (khong can OTP)
- Kiem tra trung username/email

### 2.3 PUT `/admin/users/{user_id}/role`

**Muc dich:** Cap nhat role nguoi dung.

**Request Body:**
```json
{
  "role": "admin"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Da doi role tai khoan 'nguoidung' thanh 'admin'.",
  "role": "admin"
}
```

### 2.4 POST `/admin/users/{user_id}/toggle-active`

**Muc dich:** Kich hoat / vo hieu hoa tai khoan.

**Response (200):**
```json
{
  "status": "success",
  "message": "Tai khoan nguoidung da duoc vo hieu hoa.",
  "is_active": false
}
```

### 2.5 DELETE `/admin/users/{user_id}`

**Muc dich:** Xoa nguoi dung.

**Quy tac bao ve:**
- Khong cho xoa tai khoan admin mac dinh `abc1`
- Khi xoa: xoa tokens, cap nhat activity_logs/detections/video_jobs (SET NULL user_id)

**Response (200):**
```json
{
  "status": "success",
  "message": "Da xoa tai khoan 'nguoidung' thanh cong."
}
```

---

## 3. Detection Verification Flow

### 3.1 GET `/admin/detections/unverified`

**Muc dich:** Lay danh sach detections chua duoc xac minh.

**Query Parameters:**
- `skip`: So ban ghi bo qua (default: 0)
- `limit`: So ban ghi lay (default: 20)

**Response (200):**
```json
[
  {
    "id": 42,
    "plate_text": "51A-12345",
    "plate_confidence": 0.92,
    "image_path": "/static/snapshots/abc-123.jpg",
    "source_type": "camera",
    "created_at": "2026-07-10 14:30:00"
  }
]
```

**Logic:** Su dung subquery de loai bo detections da co trong predictions:
```python
subq = db.query(Prediction.detection_id).subquery()
items = db.query(Detection).filter(~Detection.id.in_(db.query(subq)))
```

### 3.2 POST `/admin/verify-detection`

**Muc dich:** Xac minh ket qua nhan dien (Dung/Sai).

**Request Body:**
```json
{
  "detection_id": 42,
  "correct_plate": "51A-12345",
  "is_correct": 1
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Da xac minh ket qua nhan dien thanh cong."
}
```

**Quy tac:**
- Moi detection chi duoc xac minh 1 lan boi moi nguoi dung
- Kiem tra `verified_by` user ton tai trong DB
- Neu `verified_by` khong ton tai -> tim admin dau tien hoac user dau tien
- Cap nhat Statistic hang ngay:
  - `is_correct=1`: tang `correct_count`, giam `unverified_count`
  - `is_correct=0`: tang `incorrect_count`, giam `unverified_count`
- Ghi nhat ky hoat dong

### 3.3 DELETE `/admin/detections/{detection_id}`

**Muc dich:** Xoa ban ghi nhan dien khoi database.

**Quy tac:**
1. Xoa file snapshot anh neu ton tai tren disk
2. Xoa Prediction lien quan (neu da verify)
3. Cap nhat Statistic hang ngay (giam correct/incorrect_count)
4. Xoa Detection
5. Ghi nhat ky hoat dong

---

## 4. Activity Log Tracking

### 4.1 GET `/admin/activity-logs`

**Muc dich:** Lay nhat ky hoat dong.

**Query Parameters:**
- `skip`: So ban ghi bo qua (default: 0)
- `limit`: So ban ghi lay (default: 20)

**Response (200):**
```json
[
  {
    "id": 1,
    "user_email": "admin@lpr.vn",
    "action": "Dang nhap",
    "detail": "Tai khoan 'abc1' dang nhap thanh cong (role: admin).",
    "ip_address": "127.0.0.1",
    "created_at": "2026-07-10 14:30:00"
  },
  {
    "id": 2,
    "user_email": null,
    "action": "Xac minh bien so",
    "detail": "Bien so '51A-12345' (Detection #42) duoc danh gia DUNG.",
    "ip_address": "",
    "created_at": "2026-07-10 14:35:00"
  }
]
```

**Ghi chu:** `user_email` lay tu relationship `ActivityLog.user.email`. Neu user da bi xoa -> `user_email = null`.

---

## 5. Search/Filter Capabilities

### 5.1 GET `/admin/detections/search`

**Muc dich:** Tim kiem detections voi bo loc da dang.

**Query Parameters:**

| Param | Kieu | Mo ta |
|---|---|---|
| `plate` | string | Tim kiem theo bien so (ILIKE %plate%) |
| `source_type` | string | Loc theo nguon: camera, image, video |
| `date_from` | string | Tu ngay (YYYY-MM-DD) |
| `date_to` | string | Den ngay (YYYY-MM-DD) |
| `verified` | string | "yes"=da xac minh, "no"=chua xac minh |
| `region_id` | integer | Loc theo phan vung |
| `skip` | integer | So ban ghi bo qua |
| `limit` | integer | So ban ghi lay |

**Response (200):**
```json
[
  {
    "id": 42,
    "plate_text": "51A-12345",
    "plate_confidence": 0.92,
    "image_path": "/static/snapshots/abc-123.jpg",
    "source_type": "camera",
    "region_id": 1,
    "created_at": "2026-07-10 14:30:00"
  }
]
```

**Logic filter:**
```python
if plate:
    query = query.filter(Detection.plate_text.ilike(f"%{plate}%"))
if source_type:
    query = query.filter(Detection.source_type == source_type)
if region_id is not None:
    query = query.filter(Detection.region_id == region_id)
if date_from:
    query = query.filter(Detection.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
if date_to:
    query = query.filter(Detection.created_at < datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1))
if verified == "yes":
    query = query.filter(Detection.id.in_(subq))
elif verified == "no":
    query = query.filter(~Detection.id.in_(subq))
```

### 5.2 GET `/admin/regions-stats`

**Muc dich:** Thong ke so luong detection theo khu vuc.

**Response (200):**
```json
[
  { "region": "Camera Cổng Chính (Gate 1)", "count": 450 },
  { "region": "Camera Cổng Phụ (Gate 2)", "count": 320 },
  { "region": "Camera Hầm Gửi Xe A", "count": 280 },
  { "region": "Camera Hammable Gửi Xe B", "count": 184 }
]
```

**Logic:** Su dung LEFT JOIN de bao gom ca region khong co detection:
```python
rows = db.query(
    Region.name,
    func.count(Detection.id).label("count")
).outerjoin(
    Detection, Detection.region_id == Region.id
).group_by(Region.name).all()
```
