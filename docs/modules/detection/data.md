# Detection Module - Data Specification

**Module:** Nhan dien bien so xe  
**Tables:** detections, predictions, video_jobs, statistics

---

## 1. Detection Table Schema

```sql
CREATE TABLE detections (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER REFERENCES users(id) ON DELETE SET NULL,
    plate_text        VARCHAR(20) NOT NULL,
    plate_confidence  FLOAT NOT NULL,
    alt_text          VARCHAR(20),
    alt_confidence    FLOAT,
    total_frames      INTEGER DEFAULT 0,
    frame_start       INTEGER,
    frame_end         INTEGER,
    region_id         INTEGER REFERENCES regions(id) ON DELETE SET NULL,
    image_path        VARCHAR(500),
    source_type       VARCHAR(20) NOT NULL DEFAULT 'camera',
    video_job_id      INTEGER REFERENCES video_jobs(id) ON DELETE SET NULL,
    created_at        TIMESTAMP DEFAULT NOW()
);
```

### 1.1 Field Definitions

| Field | Kieu du lieu | Mo ta |
|---|---|---|
| `id` | INTEGER (PK) | ID tu tang |
| `user_id` | INTEGER (FK -> users) | Nguoi dung tao ra detection (SET NULL neu xoa) |
| `plate_text` | VARCHAR(20) | Bien so nhan dien duoc (primary result) |
| `plate_confidence` | FLOAT | Do tin cay (0.0 - 1.0) |
| `alt_text` | VARCHAR(20) | Bien so thay the (runner-up tu character voting) |
| `alt_confidence` | FLOAT | Confidence cua alt_text |
| `total_frames` | INTEGER | Tong so frame phat hien duoc (video/realtime) |
| `frame_start` | INTEGER | Frame bat dau phat hien |
| `frame_end` | INTEGER | Frame ket thuc phat hien |
| `region_id` | INTEGER (FK -> regions) | Phan vung camera (SET NULL neu xoa) |
| `image_path` | VARCHAR(500) | Duong dan anh snapshot (/static/snapshots/xxx.jpg) |
| `source_type` | VARCHAR(20) | Nguon: 'camera', 'image', 'video' |
| `video_job_id` | INTEGER (FK -> video_jobs) | ID job video lien quan |
| `created_at` | TIMESTAMP | Thoi gian tao (auto) |

### 1.2 Indexes

- `ix_detections_id` (PRIMARY KEY)
- `ix_detections_plate_text` (on plate_text)
- `ix_detections_created_at` (on created_at)

### 1.3 Source Types

| Gia tri | Mo ta | Vi du |
|---|---|---|
| `camera` | Nhan dien thoi gian thuc tu webcam | WebSocket realtime |
| `image` | Upload anh tinh | POST /predict-image |
| `video` | Upload video | POST /predict-video |

---

## 2. Prediction Table Schema

```sql
CREATE TABLE predictions (
    id              SERIAL PRIMARY KEY,
    detection_id    INTEGER NOT NULL REFERENCES detections(id) ON DELETE CASCADE,
    verified_by     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plate_text      VARCHAR(20) NOT NULL,
    predicted_text  VARCHAR(20) NOT NULL,
    is_correct      SMALLINT NOT NULL,
    verified_at     TIMESTAMP DEFAULT NOW()
);
```

### 2.1 Field Definitions

| Field | Kieu du lieu | Mo ta |
|---|---|---|
| `id` | INTEGER (PK) | ID tu tang |
| `detection_id` | INTEGER (FK -> detections) | Detection duoc xac minh (CASCADE DELETE) |
| `verified_by` | INTEGER (FK -> users) | Nguoi dung xac minh (CASCADE DELETE) |
| `plate_text` | VARCHAR(20) | Bien so dung (admin nhap) |
| `predicted_text` | VARCHAR(20) | Bien so he thong nhan dien duoc |
| `is_correct` | SMALLINT | 1=Dung, 0=Sai |
| `verified_at` | TIMESTAMP | Thoi gian xac minh (auto) |

### 2.2 Indexes

- `ix_predictions_id` (PRIMARY KEY)

### 2.3 Unique Constraint

- Moi detection chi duoc xac minh **1 lan** boi moi nguoi dung
- Kiem tra: `Prediction.detection_id + Prediction.verified_by`

---

## 3. VideoJob Table Schema

```sql
CREATE TABLE video_jobs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    filename        VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    file_size       BIGINT,
    duration        FLOAT,
    fps             FLOAT,
    total_frames    INTEGER,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress        SMALLINT DEFAULT 0,
    current_frame   INTEGER DEFAULT 0,
    error_message   TEXT,
    output_csv      VARCHAR(500),
    output_xlsx     VARCHAR(500),
    output_video    VARCHAR(500),
    created_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP
);
```

### 3.1 Field Definitions

| Field | Kieu du lieu | Mo ta |
|---|---|---|
| `id` | INTEGER (PK) | ID tu tang |
| `user_id` | INTEGER (FK -> users) | Nguoi dung upload video |
| `filename` | VARCHAR(255) | Ten file goc |
| `file_path` | VARCHAR(500) | Duong dan file tam thoi |
| `file_size` | BIGINT | Kich thuoc file (bytes) |
| `duration` | FLOAT | Thoi luong video (giay) |
| `fps` | FLOAT | FPS cua video goc |
| `total_frames` | INTEGER | Tong so frame |
| `status` | VARCHAR(20) | Trang thai: pending, processing, completed, failed |
| `progress` | SMALLINT | Tien trinh (0-100%) |
| `current_frame` | INTEGER | Frame dang xu ly |
| `error_message` | TEXT | Loi neu status=failed |
| `output_csv` | VARCHAR(500) | Duong dan file CSV ket qua |
| `output_xlsx` | VARCHAR(500) | Duong dan file Excel ket qua |
| `output_video` | VARCHAR(500) | Duong dan video ket qua da annotate |
| `created_at` | TIMESTAMP | Thoi gian tao |
| `completed_at` | TIMESTAMP | Thoi gian hoan thanh |

### 3.2 Status Flow

```
pending -> processing -> completed
                   \-> failed
```

---

## 4. Statistics Table Schema

```sql
CREATE TABLE statistics (
    id                SERIAL PRIMARY KEY,
    stat_date         DATE NOT NULL UNIQUE DEFAULT CURRENT_DATE,
    total_detections  INTEGER NOT NULL DEFAULT 0,
    unique_plates     INTEGER NOT NULL DEFAULT 0,
    avg_confidence    FLOAT NOT NULL DEFAULT 0.0,
    correct_count     INTEGER NOT NULL DEFAULT 0,
    incorrect_count   INTEGER NOT NULL DEFAULT 0,
    unverified_count  INTEGER NOT NULL DEFAULT 0,
    updated_at        TIMESTAMP DEFAULT NOW()
);
```

### 4.1 Field Definitions

| Field | Kieu du lieu | Mo ta |
|---|---|---|
| `id` | INTEGER (PK) | ID tu tang |
| `stat_date` | DATE (UQ) | Ngay (1 ban ghi/ngay) |
| `total_detections` | INTEGER | Tong so luot nhan dien |
| `unique_plates` | INTEGER | So bien so duy nhat |
| `avg_confidence` | FLOAT | Confidence trung binh |
| `correct_count` | INTEGER | So luot xac minh dung |
| `incorrect_count` | INTEGER | So luot xac minh sai |
| `unverified_count` | INTEGER | So luot chua xac minh |
| `updated_at` | TIMESTAMP | Thoi gian cap nhat cuoi |

---

## 5. Request/Response Schemas

### 5.1 PlatePrediction

```python
class PlatePrediction(BaseModel):
    bbox: List[int]     # [x1, y1, x2, y2]
    text: str           # Bien so nhan dien duoc
    conf: float         # Confidence (0.0 - 1.0)
```

### 5.2 DetectionBase

```python
class DetectionBase(BaseModel):
    plate_text: str
    plate_confidence: float
    alt_text: Optional[str] = None
    alt_confidence: Optional[float] = None
    image_path: Optional[str] = None
    source_type: str = "camera"
```

### 5.2 DetectionCreate

```python
class DetectionCreate(DetectionBase):
    pass
```

### 5.3 DetectionResponse

```python
class DetectionResponse(DetectionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

### 5.4 Image Prediction Response

```json
{
  "status": "success",
  "results": [
    {
      "bbox": [100, 50, 350, 120],
      "text": "51A-12345",
      "conf": 0.92,
      "char_confs": [0.95, 0.98, 0.89, 0.91, 0.93, 0.97, 0.95, 0.88]
    }
  ],
  "annotated_image": "/static/snapshots/abc-123.jpg"
}
```

### 5.5 Video Prediction Response

```json
{
  "status": "success",
  "task_id": "42",
  "message": "Bat dau xu ly video."
}
```

### 5.6 Video Task Status Response

```json
{
  "task_id": "42",
  "status": "processing",
  "progress": 45,
  "fps": 2.3,
  "current_frame": 450,
  "total_frames": 1000,
  "error": null
}
```

### 5.7 WebSocket Response

```json
{
  "status": "success",
  "results": [
    {
      "text": "51A-12345",
      "conf": 0.92,
      "alt_text": "51A-12346",
      "alt_confidence": 0.78,
      "hit_count": 8,
      "bbox": [100, 50, 350, 120],
      "format_score": 25,
      "total_frames": 8,
      "frame_start": 10,
      "frame_end": 18
    }
  ],
  "active_plates": [
    {
      "text": "29B1-67890",
      "conf": 0.85,
      "bbox": [200, 100, 400, 180],
      "hit_count": 3
    }
  ]
}
```

---

## 6. Data Flow Diagram

### 6.1 Image -> Detection

```
Upload Image
    │
    ▼
LPRPipeline.run_inference(image)
    │
    ├──> [{ bbox, text, conf, char_confs }]
    │
    ▼
save_snapshot_image() -> /static/snapshots/{UUID}.jpg
    │
    ▼
INSERT INTO detections (
    plate_text, plate_confidence, image_path,
    source_type='image', user_id, region_id
)
    │
    ▼
Response: { results, annotated_image }
```

### 6.2 Video -> Detection

```
Upload Video
    │
    ▼
INSERT INTO video_jobs (status='pending')
    │
    ▼
Background Thread:
    │
    ├──> For each frame:
    │       LPRPipeline.run_inference()
    │       CentroidTracker.update()
    │       IF finalized:
    │           save_snapshot_image()
    │           INSERT INTO detections (
    │               plate_text, plate_confidence, alt_text,
    │               alt_confidence, total_frames, frame_start,
    │               frame_end, image_path, source_type='video',
    │               video_job_id, user_id, region_id
    │           )
    │
    ├──> Flush merged buffer:
    │       INSERT remaining detections
    │
    └──> UPDATE video_jobs SET status='completed'
```

### 6.3 Verification -> Prediction + Statistics

```
Admin Verify Detection
    │
    ▼
INSERT INTO predictions (
    detection_id, verified_by, plate_text,
    predicted_text, is_correct
)
    │
    ▼
UPDATE statistics:
    IF is_correct == 1:
        correct_count += 1
    ELSE:
        incorrect_count += 1
    unverified_count -= 1
```
