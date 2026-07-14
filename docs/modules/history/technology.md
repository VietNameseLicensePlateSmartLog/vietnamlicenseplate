# History Module - Technology Specification

**Module:** Lich su nhan dien  
**Files:** `services/history_service.py`, `routes/history.py`, `controllers/history_controller.py`

---

## 1. SQLAlchemy Filter Patterns

### 1.1 Basic Query

```python
from sqlalchemy.orm import Session
from src.models import models

class HistoryService:
    @staticmethod
    def get_history(user_id: int | None, skip: int, limit: int, db: Session):
        query = db.query(models.Detection)
        if user_id is not None:
            query = query.filter(models.Detection.user_id == user_id)
        return query.order_by(models.Detection.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
```

### 1.2 Filter Patterns

```python
# Filter theo user ID
query = query.filter(models.Detection.user_id == user_id)

# Filter theo bien so (case-insensitive)
query = query.filter(models.Detection.plate_text.ilike(f"%{plate}%"))

# Filter theo nguon
query = query.filter(models.Detection.source_type == source_type)

# Filter theo ngay
query = query.filter(models.Detection.created_at >= dt_from)
query = query.filter(models.Detection.created_at < dt_to)

# Filter theo region
query = query.filter(models.Detection.region_id == region_id)

# Filter da xac minh
subq = db.query(models.Prediction.detection_id).subquery()
query = query.filter(models.Detection.id.in_(db.query(subq)))

# Filter chua xac minh
query = query.filter(~models.Detection.id.in_(db.query(subq)))
```

### 1.3 Ordering

```python
# Moi nhat truoc (giam dan)
query = query.order_by(models.Detection.created_at.desc())

# Cu nhat truoc (tang dan)
query = query.order_by(models.Detection.created_at.asc())
```

---

## 2. Pagination Implementation

### 2.1 Offset/Limit

```python
# Phan trang bang offset va limit
results = query.offset(skip).limit(limit).all()
```

### 2.2 Frontend Pagination

```typescript
// React component
const [page, setPage] = useState(1);
const [data, setData] = useState([]);
const pageSize = 20;

const fetchHistory = async (page: number) => {
    const skip = (page - 1) * pageSize;
    const response = await fetch(
        `${API_BASE}/history?skip=${skip}&limit=${pageSize}&user_id=${userId}`
    );
    const result = await response.json();
    setData(result);
};

// Kiem tra con du lieu khong
const hasMore = data.length === pageSize;
```

### 2.3 Infinite Scroll (Frontend)

```typescript
// Load more khi cuon xuong
const handleScroll = () => {
    if (
        window.innerHeight + window.scrollY >= document.body.offsetHeight - 500
        && hasMore
        && !loading
    ) {
        setPage(prev => prev + 1);
    }
};

useEffect(() => {
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
}, [hasMore, loading]);
```

---

## 3. Delete Implementation

### 3.1 Service Layer

```python
import os
from fastapi import HTTPException

class HistoryService:
    @staticmethod
    def delete_history(id: int, db: Session):
        item = db.query(models.Detection).filter(models.Detection.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Khong tim thay ban ghi lich su.")

        # Xoa file anh snapshot
        if item.image_path:
            local_img_path = item.image_path.lstrip('/')
            if os.path.exists(local_img_path):
                try:
                    os.remove(local_img_path)
                except Exception:
                    pass

        # Xoa DB record
        db.delete(item)
        db.commit()
        return {"status": "success", "message": f"Da xoa thanh cong ban ghi ID={id}"}
```

### 3.2 File Path Conversion

```python
# Duong dan trong DB: "/static/snapshots/xxx.jpg"
# Duong dan tren disk: "static/snapshots/xxx.jpg"

local_img_path = item.image_path.lstrip('/')
```

### 3.3 Error Handling

```python
# File khong ton tai -> van xoa DB
if os.path.exists(local_img_path):
    try:
        os.remove(local_img_path)
    except Exception:
        pass  # Khong block xoa DB

# Detection khong ton tai -> 404
if not item:
    raise HTTPException(status_code=404, detail="Khong tim thay ban ghi lich su.")
```

---

## 4. Controller Layer

### 4.1 History Controller

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.services.history_service import HistoryService

class HistoryController:
    @staticmethod
    def get_history(user_id: int | None, skip: int, limit: int, db: Session):
        return HistoryService.get_history(user_id, skip, limit, db)

    @staticmethod
    def delete_history(detection_id: int, db: Session):
        return HistoryService.delete_history(detection_id, db)
```

### 4.2 Route Layer

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.history_controller import HistoryController

router = APIRouter(tags=["History"])

@router.get("/history")
def get_history(
    user_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    return HistoryController.get_history(user_id, skip, limit, db)

@router.delete("/history/{detection_id}")
def delete_history(detection_id: int, db: Session = Depends(get_db)):
    return HistoryController.delete_history(detection_id, db)
```

---

## 5. Performance Considerations

### 5.1 Indexes

```sql
-- Tong hop cho ca history va admin search
CREATE INDEX ix_detections_created_at ON detections(created_at);
CREATE INDEX ix_detections_plate_text ON detections(plate_text);
CREATE INDEX ix_detections_id ON detections(id);
```

### 5.2 Query Optimization

```python
# Su dung索引 created_at cho ordering
query.order_by(Detection.created_at.desc())  # Uses ix_detections_created_at

# Su dung索引 plate_text cho search
query.filter(Detection.plate_text.ilike(f"%{plate}%"))  # Uses ix_detections_plate_text

# Limit results de tranh load qua nhieu
query.limit(limit)  # Default: 20
```

### 5.3 N+1 Prevention

```python
# DON'T: Query user cho moi detection
for d in detections:
    user = db.query(User).filter(User.id == d.user_id).first()  # N+1!

# DO: Join truoc
results = db.query(Detection, User.username).outerjoin(
    User, Detection.user_id == User.id
).all()
```
