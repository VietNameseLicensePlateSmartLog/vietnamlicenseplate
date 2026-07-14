# System Architecture Overview

**Du an:** Vietnam License Plate Recognition (LPR)  
**Phien ban:** 1.0.0  
**Ngay tao:** 2026-07-10

---

## 1. Kien truc MVC (Model-View-Controller)

He thong backend duoc xay dung theo kien truc MVC voi 4 lop chinh:

```
┌──────────────────────────────────────────────────────────────┐
│                       CLIENT (Browser)                        │
│                   Next.js App Router (Port 3000)              │
│    ┌──────────┐  ┌──────────┐  ┌──────────────────────┐     │
│    │ ImageTab  │  │ VideoTab │  │   RealtimeTab         │     │
│    │  (Anh)    │  │ (Video)  │  │ (WebSocket + Webcam)  │     │
│    └─────┬─────┘  └────┬─────┘  └──────────┬───────────┘     │
│          └──────────────┴───────────────────┘                 │
└─────────────────────────────┬────────────────────────────────┘
                              │ HTTP / WebSocket
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI Port 8000)                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    ROUTES (View Layer)                    │ │
│  │  auth.py  |  predict.py  |  admin.py  |  regions.py  |  │ │
│  │                        history.py                        │ │
│  └──────────────────────────┬──────────────────────────────┘ │
│                             │                                 │
│  ┌──────────────────────────┴──────────────────────────────┐ │
│  │               CONTROLLERS (Controller Layer)             │ │
│  │  auth_controller  |  predict_controller  |               │ │
│  │  admin_controller |  region_controller  |                │ │
│  │                      history_controller                  │ │
│  └──────────────────────────┬──────────────────────────────┘ │
│                             │                                 │
│  ┌──────────────────────────┴──────────────────────────────┐ │
│  │               SERVICES (Business Logic Layer)            │ │
│  │  auth_service  |  predict_service  |  admin_service      │ │
│  │  region_service |  history_service                       │ │
│  │  ai_pipeline   |  preprocessing  |  validation           │ │
│  │  tracking                                                │ │
│  └──────────────────────────┬──────────────────────────────┘ │
│                             │                                 │
│  ┌──────────────────────────┴──────────────────────────────┐ │
│  │               MODELS (Data Layer - ORM)                   │ │
│  │  models.py (8 ORM tables)  |  schemas.py (Pydantic)     │ │
│  └──────────────────────────┬──────────────────────────────┘ │
│                             │                                 │
│  ┌──────────────────────────┴──────────────────────────────┐ │
│  │               DATABASE (PostgreSQL 14+)                   │ │
│  │  users | detections | predictions | regions              │ │
│  │  video_jobs | statistics | tokens | activity_logs        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │               UTILITIES                                   │ │
│  │  security.py (PBKDF2)  |  email.py (SMTP)               │ │
│  │  helpers.py (snapshot, cleanup, activity log)             │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 1.1 Phan lop chi tiet

| Lop | Thu muc | Trach nhiem |
|---|---|---|
| **Routes** | `src/routes/` | Dinh nghia API endpoints, xac thuc request, goi controller |
| **Controllers** | `src/controllers/` | Dieu phoi request, goi service, xu ly response |
| **Services** | `src/services/` | Business logic, xu ly AI pipeline, tracking, validation |
| **Models** | `src/models/` | ORM models (models.py), Pydantic schemas (schemas.py) |
| **Config** | `src/config/` | Settings (env vars), Database (SQLAlchemy engine) |
| **Utils** | `src/utils/` | Security, email, helpers (snapshot, cleanup, activity log) |

---

## 2. AI Pipeline: 3 Giai Doan YOLOv8

```
Anh dau vao (1280px cho anh, 1024px cho video, 640px cho realtime)
    │
    ▼
┌──────────────────────────────────────┐
│  STAGE 1: Plate Detection             │  YOLOv8 Object Detection
│  Model: stage1_detector_robust.pt     │  Input: anh goc (1280/1024/640px)
│  NMS: IoU threshold = 0.5             │  Conf: 0.6 (anh) / 0.5 (video)
│  Output: bounding box bien so         │
└──────────────────┬───────────────────┘
                   │ Cat tung bien so
                   ▼
┌──────────────────────────────────────┐
│  PREPROCESSING                         │
│  1. Deskew (OTSU -> minAreaRect)      │  Xoay bien so ve phuong ngang (±45°)
│  2. Pad +8px                          │  Them padding xung quanh
│  3. Preprocess (Grayscale -> Sharpen) │  Lam sach anh
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  STAGE 2: Character Detection         │  YOLOv8 Object Detection
│  Model: stage2_char_detector.pt       │  Input: anh bien so (640px)
│  NMS: IoU threshold = 0.3             │  Conf: 0.5 / 0.8
│  Filter: box nho < 40% avg            │
│  Sort: theo hang (Y-gap)              │
└──────────────────┬───────────────────┘
                   │ Cat tung ky tu -> Resize 64x64
                   ▼
┌──────────────────────────────────────┐
│  STAGE 3: Character Classification    │  YOLOv8 Classification
│  Model: stage3_char_classify.pt       │  Input: anh ky tu 64x64
│  - Phan loai tren anh GOC             │  Conf: 0.3 / 0.7
│  - Lay alternatives cho format        │
│    correction                         │
└──────────────────┬───────────────────┘
                   │ Validate format VN
                   │ Format Correction (pos-based)
                   │ Ghep chuoi theo thu tu
                   ▼
            Ket qua: "51A-12345"
            Confidence: Geometric Mean
```

### 2.1 Flow chi tiet

1. **Stage 1:** Phat hien bien so tren anh goc voi imgsz=1280 (anh) / 1024 (video) / 640 (realtime)
2. **NMS Stage 1:** Loai bo box trung lap voi IoU > 0.5
3. **Crop:** Cat tung bien so tu anh goc
4. **Deskew:** Xoay bien so ve phuong ngang su dung OTSU + minAreaRect
5. **Pad:** Them 8px padding xung quanh
6. **Preprocess:** Grayscale -> Sharpen -> RGB
7. **Stage 2:** Phat hien ky tu tren anh bien so voi imgsz=640
8. **NMS Stage 2:** Loai bo box trung lap voi IoU > 0.3
9. **Filter:** Loai bo box nho (< 40% dien tích trung binh)
10. **Sort:** Sap xep ky tu theo hang (tach 2 dòng theo Y-gap, sort trai->phai)
11. **Stage 3:** Phan loai tung ky tu (64x64), lay top-2 alternatives
12. **Format Correction:** Sua ky tu sai based on position (pos0-1=so, pos2=chu, pos4+=so)
13. **Validation:** Kiem tra format bien so VN
14. **Confidence:** Geometric Mean cua confidence tung ky tu

---

## 3. Entity Relationship Diagram (ERD)

```
┌─────────────────────┐       ┌─────────────────────────┐
│       users          │       │        regions            │
├─────────────────────┤       ├─────────────────────────┤
│ id (PK)             │       │ id (PK)                  │
│ username (UQ)       │       │ name                     │
│ email (UQ)          │       │ location                 │
│ password_hash       │       │ is_active                │
│ full_name           │       │ created_at               │
│ role                │       └──────────┬──────────────┘
│ is_verified         │                  │
│ is_active           │                  │ 1:N
│ failed_attempts     │                  │
│ last_login_at       │                  ▼
│ last_logout_at      │       ┌─────────────────────────┐
│ created_at          │       │      detections           │
│ updated_at          │       ├─────────────────────────┤
└──────┬──────────────┘       │ id (PK)                  │
       │                      │ user_id (FK -> users)     │
       │ 1:N                  │ plate_text                │
       │                      │ plate_confidence          │
       ▼                      │ alt_text                  │
┌─────────────────────┐       │ alt_confidence            │
│      tokens          │       │ total_frames              │
├─────────────────────┤       │ frame_start               │
│ id (PK)             │       │ frame_end                 │
│ user_id (FK->users) │       │ region_id (FK->regions)   │
│ token               │       │ image_path                │
│ type                │       │ source_type               │
│ expires_at          │       │ video_job_id (FK->jobs)   │
│ is_used             │       │ created_at                │
│ created_at          │       └──────────┬──────────────┘
└─────────────────────┘                  │
                                         │ 1:N
┌─────────────────────┐                  ▼
│   activity_logs      │       ┌─────────────────────────┐
├─────────────────────┤       │      predictions          │
│ id (PK)             │       ├─────────────────────────┤
│ user_id (FK->users) │       │ id (PK)                  │
│ action              │       │ detection_id (FK->det.)   │
│ detail              │       │ verified_by (FK->users)   │
│ ip_address          │       │ plate_text                │
│ created_at          │       │ predicted_text            │
└─────────────────────┘       │ is_correct                │
                              │ verified_at               │
┌─────────────────────┐       └─────────────────────────┘
│    video_jobs        │
├─────────────────────┤       ┌─────────────────────────┐
│ id (PK)             │       │     statistics            │
│ user_id (FK->users) │       ├─────────────────────────┤
│ filename            │       │ id (PK)                  │
│ file_path           │       │ stat_date (UQ)           │
│ file_size           │       │ total_detections         │
│ duration            │       │ unique_plates            │
│ fps                 │       │ avg_confidence           │
│ total_frames        │       │ correct_count            │
│ status              │       │ incorrect_count          │
│ progress            │       │ unverified_count         │
│ current_frame       │       │ updated_at               │
│ error_message       │       └─────────────────────────┘
│ output_csv          │
│ output_xlsx         │
│ output_video        │
│ created_at          │
│ completed_at        │
└─────────────────────┘
```

### 3.1 Quan he

| Quan he | Bang cha | Bang con | Kieu | FK |
|---|---|---|---|---|
| User - Token | users | tokens | 1:N | user_id |
| User - Detection | users | detections | 1:N | user_id |
| User - ActivityLog | users | activity_logs | 1:N | user_id |
| User - VideoJob | users | video_jobs | 1:N | user_id |
| User - Prediction | users | predictions | 1:N | verified_by |
| Region - Detection | regions | detections | 1:N | region_id |
| VideoJob - Detection | video_jobs | detections | 1:N | video_job_id |
| Detection - Prediction | detections | predictions | 1:N | detection_id |

---

## 4. API Map

Tat API nam duoi tien to `/api/v1`.

### 4.1 Auth (`/api/v1/auth`)

```
POST   /auth/register          Dang ky tai khoan -> gui OTP
POST   /auth/verify-otp        Xac thuc OTP kich hoat tai khoan
POST   /auth/resend-otp        Gui lai OTP
POST   /auth/login             Dang nhap
POST   /auth/forgot-password   Gui OTP khôi phục mat khau
POST   /auth/reset-password    Dat lai mat khau
POST   /auth/logout            Dang xuat
GET    /auth/test-email        Test SMTP connection
```

### 4.2 Prediction (`/api/v1`)

```
POST   /predict-image          Upload anh de nhan dien
POST   /predict-video          Upload video de xu ly (background thread)
GET    /tasks/{task_id}        Kiem tra tien trinh video
GET    /tasks/{task_id}/download  Tai video ket qua
WS     /ws/lpr                 WebSocket nhan dien thoi gian thuc
```

### 4.3 Admin (`/api/v1/admin`)

```
GET    /admin/stats                        Thong ke tong quan dashboard
GET    /admin/users                        Danh sach nguoi dung
POST   /admin/users                        Tao tai khoan moi
PUT    /admin/users/{id}/role              Cap nhat role
POST   /admin/users/{id}/toggle-active     Kich hoat/vo hieu hoa
DELETE /admin/users/{id}                   Xoa nguoi dung
GET    /admin/detections/unverified        Danh sach chua xac minh
POST   /admin/verify-detection             Xac minh ket qua (dung/sai)
DELETE /admin/detections/{id}              Xoa detection
GET    /admin/detections/search            Tim kiem detections
GET    /admin/regions-stats                Thong ke theo khu vuc
GET    /admin/activity-logs                Nhat ky hoat dong
```

### 4.4 Regions (`/api/v1`)

```
GET    /regions                Danh sach phan vung camera
```

### 4.5 History (`/api/v1`)

```
GET    /history                Lich su nhan dien (filter + pagination)
DELETE /history/{id}           Xoa ban ghi nhan dien
```

---

## 5. Data Flow

### 5.1 Image Prediction

```
User upload anh
    │
    ▼
Frontend (ImageTab.tsx)
    │ POST /api/v1/predict-image (multipart/form-data)
    │
    ▼
FastAPI Route (routes/predict.py)
    │
    ▼
Controller (predict_controller.py)
    │
    ▼
Service (predict_service.py)
    │
    ├──> init_lpr_service() -> LPRPipeline (singleton)
    │         │
    │         ├──> Stage 1: YOLOv8 predict (1280px)
    │         ├──> Deskew + Pad + Preprocess
    │         ├──> Stage 2: YOLOv8 predict (640px)
    │         ├──> Stage 3: YOLOv8 predict (64x64)
    │         └──> Validation + Format Correction
    │
    ├──> draw_plate_results() -> annotated image
    ├──> save_snapshot_image() -> luu vao static/snapshots/
    ├──> Luu Detection vao DB
    │
    ▼
Response: { status, results, annotated_image }
    │
    ▼
Frontend: Hien thi ket qua voi bounding box
```

### 5.2 Video Prediction

```
User upload video
    │
    ▼
Frontend (VideoTab.tsx)
    │ POST /api/v1/predict-video (multipart/form-data)
    │
    ▼
FastAPI Route -> Controller -> Service
    │
    ├──> Tao VideoJob trong DB (status=pending)
    ├──> Luu file vao temp directory
    ├──> Khoi chay background thread
    │
    ▼
Background Thread (process_video_background)
    │
    ├──> Mo video voi OpenCV
    ├──> Tao CentroidTracker
    ├──> Loop qua tung frame:
    │       ├──> Frame skip (xu ly ~2 FPS)
    │       ├──> LPRPipeline.run_inference()
    │       ├──> Filter valid plates (format + score)
    │       ├──> CentroidTracker.update()
    │       ├──> Luu finalized detections vao DB
    │       └──> Ghi frame output voi bbox
    │
    ├──> Flush merged buffer khi het video
    ├──> Cap nhat status=completed
    └──> Cleanup temp files
    │
    ▼
Frontend polling GET /api/v1/tasks/{id}
    │ Hien thi progress bar
    │
    ▼
Khi completed -> Tai video ket quả
```

### 5.3 WebSocket Realtime

```
User mo webcam
    │
    ▼
Frontend (RealtimeTab.tsx + useWebSocket.ts)
    │ WS /api/v1/ws/lpr
    │ Gui frame base64 + conf thresholds
    │
    ▼
WebSocket Handler (predict_service.py)
    │
    ├──> Decode base64 -> PIL.Image
    ├──> LPRPipeline.run_inference() (640px)
    ├──> Filter valid plates
    ├──> CentroidTracker.update()
    ├──> Luu finalized detections vao DB
    │
    ▼
Response: { status, results, active_plates }
    │
    ├──> results: Bien da finalize (luu DB, hien thi history)
    └──> active_plates: Bien dang track (ve bbox live)
    │
    ▼
Frontend: Hien thi live bbox + ket qua moi
```

---

## 6. Deployment Architecture

```
┌──────────────────────────────────────────────────┐
│                  DEVELOPMENT                       │
│                                                    │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  Backend (Python)  │  │  Frontend (Next.js)   │  │
│  │  Port 8000         │  │  Port 3000            │  │
│  │  Uvicorn + reload  │  │  Dev server           │  │
│  └─────────┬──────────┘  └──────────┬───────────┘  │
│            │                        │               │
│            │   Next.js rewrites     │               │
│            │   /api/v1/* -> :8000   │               │
│            │   (WebSocket + large   │               │
│            │    files: direct)      │               │
│            │                        │               │
│  ┌─────────┴────────────────────────┴───────────┐  │
│  │              PostgreSQL Database               │  │
│  │              Port 5432                         │  │
│  └───────────────────────────────────────────────┘  │
│                                                    │
│  ┌───────────────────────────────────────────────┐  │
│  │  GPU (NVIDIA RTX) hoac CPU fallback           │  │
│  │  CUDA 11.8+ / cuDNN 8.6+                     │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 6.1 Che do chay

| Che do | Lenh | Mo ta |
|---|---|---|
| **Ca hai** | `npm run dev` (root) | Chay backend + frontend cung luc (concurrently) |
| **Backend** | `python -m src.main` | Uvicorn port 8000, reload=True |
| **Frontend** | `npm run dev` | Next.js dev server port 3000 |

### 6.2 Proxy Configuration

Frontend su dung Next.js rewrites de proxy API:
- `/api/v1/*` -> `http://127.0.0.1:8000/api/v1/*`
- WebSocket: ket noi truc tiep den `ws://127.0.0.1:8000/api/v1/ws/lpr`
- Upload file lon (>10MB): ket noi truc tiep den backend

---

## 7. Module Structure

### 7.1 Backend Module Map

```
backend/src/
├── main.py                          Entry point: FastAPI app, lifespan, CORS, router
├── config/
│   ├── settings.py                  Settings (thresholds, DB, SMTP, weights path)
│   └── database.py                  SQLAlchemy engine, session, Base
├── models/
│   ├── models.py                    8 ORM models (User, Detection, Prediction, etc.)
│   └── schemas.py                   Pydantic schemas (request/response)
├── routes/
│   ├── auth.py                      /auth/* endpoints
│   ├── predict.py                   /predict-*, /tasks/*, /ws/lpr
│   ├── admin.py                     /admin/* endpoints
│   ├── regions.py                   /regions endpoint
│   └── history.py                   /history endpoints
├── controllers/
│   ├── auth_controller.py           Dieu phoi auth requests
│   ├── predict_controller.py        Dieu phoi prediction requests
│   ├── admin_controller.py          Dieu phoi admin requests
│   ├── region_controller.py         Dieu phoi region requests
│   └── history_controller.py        Dieu phoi history requests
├── services/
│   ├── ai_pipeline.py               LPRPipeline class (3-stage YOLOv8)
│   ├── preprocessing.py             Deskew, threshold, filter, pad
│   ├── validation.py                Validate format bien so VN
│   ├── tracking.py                  CentroidTracker + Character Voting
│   ├── predict_service.py           Xu ly anh/video/WebSocket
│   ├── auth_service.py              Xac thuc, JWT, OTP, phan quyen
│   ├── admin_service.py             Thong ke, quan ly user/region
│   ├── region_service.py            Truy van region
│   └── history_service.py           Truy van lich su
└── utils/
    ├── security.py                  PBKDF2 password hashing
    ├── email.py                     Gui email OTP qua SMTP Gmail
    └── helpers.py                   Snapshot, file cleanup, activity log
```

### 7.2 Frontend Module Map

```
frontend/src/
├── app/
│   ├── layout.tsx                   Root layout (font, globals.css)
│   ├── page.tsx                     Root -> redirect /login
│   ├── login/page.tsx               Trang dang nhap
│   ├── signin/page.tsx              Trang dang ky (embedded LoginModal)
│   ├── home/page.tsx                Trang chu — Tab Image/Video/Realtime
│   └── admin/                       7 trang quan tri
│       ├── layout.tsx               Layout admin (Sidebar + TopBar)
│       ├── dashboard/               Dashboard tong quan
│       ├── users/                   Quan ly nguoi dung
│       ├── verification/            Xac minh ket qua
│       ├── search/                  Tim kiem detections
│       ├── activity-log/            Nhat ky hoat dong
│       ├── prediction-ratio/        Ti le nhan dien theo nguon
│       └── variable-stats/          Thong ke bien thien confidence
├── components/
│   ├── Navbar.tsx                   Thanh dieu huong chinh
│   ├── LoginModal.tsx               Modal 5 che do (login/register/OTP/forgot/reset)
│   ├── AnimatedBackground.tsx       Hieu ung nen animation
│   ├── ImageTab.tsx                 Tab nhan dien anh
│   ├── VideoTab.tsx                 Tab nhan dien video
│   ├── RealtimeTab.tsx              Tab nhan dien thoi gian thuc
│   ├── SnapshotModal.tsx            Modal xem snapshot
│   ├── GeneralHistoryModal.tsx      Modal lich su chung
│   └── admin/
│       ├── Sidebar.tsx              Sidebar quan tri
│       └── TopBar.tsx               TopBar quan tri
├── hooks/
│   └── useWebSocket.ts              Hook WebSocket ket noi backend
├── lib/
│   ├── api.ts                       API_BASE, BACKEND_URL, WS_URL
│   └── utils.ts                     parseVnDatetime, formatVnTime
└── styles/
    └── admin.css                    CSS cho admin panel
```

---

## 8. Technology Stack

### 8.1 Backend

| Cong nghe | Phien ban | Muc dich |
|---|---|---|
| Python | 3.11+ | Ngon ngu chinh |
| FastAPI | 0.115.12 | Web framework |
| SQLAlchemy | 2.0.41 | ORM (Object-Relational Mapping) |
| Uvicorn | 0.34.2 | ASGI server |
| Pydantic | 2.x | Data validation |
| Pydantic Settings | - | Environment variable management |
| PostgreSQL | 14+ | Database |

### 8.2 AI/ML

| Cong nghe | Phien ban | Muc dich |
|---|---|---|
| Ultralytics YOLO | 8.3.163 | Object detection + classification |
| OpenCV | 4.12.0.88 | Image preprocessing |
| Pillow | 11.3.0 | Image manipulation |
| PyTorch (CUDA) | Latest | Deep learning backend |
| NumPy | - | Numerical computing |

### 8.3 Authentication

| Cong nghe | Phien ban | Muc dich |
|---|---|---|
| PyJWT | 2.10.1 | JWT token (dinh nghia nhung hien tai dung session-based) |
| PBKDF2-HMAC-SHA256 | - | Password hashing (100K iterations) |
| SMTP (Gmail) | - | Gui OTP qua email |

### 8.4 Frontend

| Cong nghe | Phien ban | Muc dich |
|---|---|---|
| Next.js | 16.2.10 | React framework (App Router) |
| React | 19.2.4 | UI library |
| TypeScript | 5.x | Type-safe JavaScript |
| Tailwind CSS | 4.x | Utility-first CSS |

---

## 9. File Storage

| Loai file | Vi tri | Mo ta |
|---|---|---|
| **Snapshot anh** | `backend/static/snapshots/{UUID}.jpg` | Anh bien so voi bounding box |
| **Model weights** | `backend/weights/*.pt` | 3 model YOLOv8 (khong commit vao git) |
| **Video input** | `{tempdir}/{uuid}_in.{ext}` | File video tam thoi |
| **Video output** | `{tempdir}/{uuid}_out.mp4` | Video da annotate |
| **Error log** | `{tempdir}/lpr_frame_errors.log` | Log loi frame |
