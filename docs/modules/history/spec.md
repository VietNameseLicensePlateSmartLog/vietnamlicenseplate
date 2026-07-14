# History Module - Functional Specification

**Module:** Lich su nhan dien  
**Route prefix:** `/api/v1`  
**Files:** `routes/history.py`, `controllers/history_controller.py`, `services/history_service.py`

---

## 1. History Listing with Filters

### 1.1 GET `/history`

**Muc dich:** Lay lich su nhan dien voi bo loc va phan trang.

**Query Parameters:**

| Param | Kieu | Mo ta | Mac dinh |
|---|---|---|---|
| `user_id` | integer | Loc theo nguoi dung (NULL = tat ca) | NULL |
| `skip` | integer | So ban ghi bo qua | 0 |
| `limit` | integer | So ban ghi lay | 20 |

**Response (200):**
```json
[
  {
    "id": 42,
    "plate_text": "51A-12345",
    "plate_confidence": 0.92,
    "alt_text": "51A-12346",
    "alt_confidence": 0.78,
    "image_path": "/static/snapshots/abc-123.jpg",
    "source_type": "camera",
    "created_at": "2026-07-10 14:30:00"
  },
  {
    "id": 41,
    "plate_text": "29B1-67890",
    "plate_confidence": 0.87,
    "alt_text": null,
    "alt_confidence": null,
    "image_path": "/static/snapshots/def-456.jpg",
    "source_type": "image",
    "created_at": "2026-07-10 14:25:00"
  }
]
```

**Logic:**
```python
query = db.query(models.Detection)
if user_id is not None:
    query = query.filter(models.Detection.user_id == user_id)
return query.order_by(models.Detection.created_at.desc())\
    .offset(skip)\
    .limit(limit)\
    .all()
```

### 1.2 Tinh nang

- **Filter theo user:** Neu `user_id` duoc cung cap, chi lay detections cua user do
- **Filter theo nguon:** Hien tai chua ho tro filter theo `source_type` (duoc xu ly o admin search)
- **Sap xep:** Theo `created_at` giam dan (moi nhat truoc)
- **Phan trang:** Su dung `skip` va `limit`
- **Snapshot xem:** Frontend hien thi anh tu `image_path`

---

## 2. Pagination

### 2.1 Implementation

Su dung `offset` va `limit` cua SQLAlchemy:

```python
query.order_by(Detection.created_at.desc())\
    .offset(skip)\
    .limit(limit)\
    .all()
```

### 2.2 Frontend Usage

```typescript
// Pagination params
const [page, setPage] = useState(1);
const pageSize = 20;

// Tinh skip
const skip = (page - 1) * pageSize;

// Fetch
const response = await fetch(`/api/v1/history?skip=${skip}&limit=${pageSize}`);
```

### 2.3 Response Format

Ket qua duoc tra ve la mang (khong co tong so ban ghi). Frontend su dung:
- Neu `results.length < pageSize` -> da het du lieu
- Neu `results.length == pageSize` -> con du lieu, hien nut "Tai them"

---

## 3. Delete Functionality

### 3.1 DELETE `/history/{detection_id}`

**Muc dich:** Xoa mot ban ghi nhan dien.

**Response (200):**
```json
{
  "status": "success",
  "message": "Da xoa thanh cong ban ghi ID=42"
}
```

**Response (404):**
```json
{
  "detail": "Khong tim thay ban ghi lich su."
}
```

### 3.2 Logic xoa

```python
@staticmethod
def delete_history(id: int, db: Session):
    item = db.query(models.Detection).filter(models.Detection.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Khong tim thay ban ghi lich su.")

    # Xoa file anh snapshot neu ton tai
    if item.image_path:
        local_img_path = item.image_path.lstrip('/')
        if os.path.exists(local_img_path):
            try:
                os.remove(local_img_path)
            except Exception:
                pass  # Khong block xoa DB neu file da bi xoa

    db.delete(item)
    db.commit()
    return {"status": "success", "message": f"Da xoa thanh cong ban ghi ID={id}"}
```

### 3.3 Quy tac xoa

1. **Tim detection** theo ID
2. **Xoa file snapshot** neu ton tai tren disk (`image_path`)
   - `image_path` co dang `/static/snapshots/xxx.jpg`
   - Chuyen sang local path: `static/snapshots/xxx.jpg`
3. **Xoa detection** khoi database
4. **Khong xoa cascade:** Prediction, VideoJob lien quan khong bi anh huong (SET NULL)

---

## 4. Chi tiet Tinh nang

### 4.1 User Scope

- **User:** Chi xem lich su cua minh (frontend gui `user_id`)
- **Admin:** Co the xem tat ca (khong gui `user_id` hoac gui `user_id=NULL`)

### 4.2 Data Display

Moi ban ghi hien thi:
- **Bien so:** `plate_text`
- **Confidence:** `plate_confidence` (0.0-1.0, frontend nhan 100 de hien thi)
- **Anh snapshot:** `image_path` (hien thi trong modal/breadcrumb)
- **Nguon:** `source_type` (camera/image/video)
- **Thoi gian:** `created_at` (format theo mui gio VN)

### 4.3 GeneralHistoryModal

Frontend co component `GeneralHistoryModal.tsx` de hien thi lich su:
- Mo tu trang Home
- Hien thi danh sach voi anh nho
- Click de xem chi tiet (snapshot voi bounding box)
- Nut xoa ban ghi
