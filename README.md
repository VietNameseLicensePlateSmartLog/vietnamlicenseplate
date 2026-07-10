# Vietnam License Plate Recognition (LPR)

Hệ thống nhận diện biển số xe Việt Nam sử dụng trí tuệ nhân tạo — tích hợp nhận diện thời gian thực qua webcam, nhận diện từ ảnh và video, quản lý người dùng, phân vùng camera, cùng bảng điều khiển quản trị toàn diện.

---

## Mục lục

- [Giới thiệu](#giới-thiệu)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Tính năng chính](#tính-năng-chính)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Hướng dẫn cài đặt](#hướng-dẫn-cài-đặt)
- [Cấu hình môi trường](#cấu-hình-môi-trường)
- [Chạy ứng dụng](#chạy-ứng-dụng)
- [API Endpoints](#api-endpoints)
- [AI Pipeline](#ai-pipeline)
- [Các kỹ thuật xử lý](#các-kỹ-thuật-xử-lý)

---

## Giới thiệu

**Vietnam LPR** là ứng dụng web fullstack giúp nhận diện tự động biển số xe Việt Nam từ nhiều nguồn khác nhau: webcam thời gian thực, ảnh tĩnh và video. Hệ thống sử dụng kiến trúc **3 giai đoạn YOLOv8** — từ phát hiện biển số, phát hiện ký tự, đến phân loại ký tự — kết hợp **Centroid Tracking + Character Voting** để tăng độ chính xác qua nhiều frame.

Hệ thống được xây dựng theo mô hình **MVC** ở backend và **Next.js App Router** ở frontend, với cơ sở dữ liệu **PostgreSQL** lưu trữ toàn bộ lịch sử nhận diện, thông tin người dùng và phân vùng camera.

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────┐
│                   FRONTEND (Next.js)                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ ImageTab │  │ VideoTab │  │    RealtimeTab          │ │
│  │  (Ảnh)   │  │  (Video) │  │  (WebSocket + Webcam)  │ │
│  └────┬─────┘  └────┬─────┘  └───────────┬────────────┘ │
│       │              │                     │              │
│       └──────────────┴─────────┬───────────┘              │
│                                │ HTTP / WebSocket         │
├────────────────────────────────┼─────────────────────────┤
│                   BACKEND (FastAPI)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Auth    │  │ Predict  │  │  Admin   │  │ History  │ │
│  │Controller│  │Controller│  │Controller│  │Controller│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │              │              │              │       │
│  ┌────┴──────────────┴──────────────┴──────────────┴───┐ │
│  │              Service Layer (Business Logic)           │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                 │
│  ┌──────────────────────┴──────────────────────────────┐ │
│  │         AI Pipeline (3-Stage YOLOv8)                 │ │
│  │  Stage 1: Phát hiện biển số                         │ │
│  │  → Deskew + Pad + Preprocess                        │ │
│  │  → Stage 2: Phát hiện ký tự                         │ │
│  │  → Stage 3: Phân loại ký tự (Character Classification)  │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                 │
│  ┌──────────────────────┴──────────────────────────────┐ │
│  │     Centroid Tracking + Character Voting             │ │
│  │  Theo dõi biển số qua frame, gộp kết quả voting     │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                 │
│  ┌──────────────────────┴──────────────────────────────┐ │
│  │              PostgreSQL Database                     │ │
│  │  users | detections | predictions | video_jobs      │ │
│  │  regions | statistics | tokens | activity_logs      │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Công nghệ sử dụng

| Lớp | Công nghệ | Phiên bản |
|---|---|---|
| **Frontend** | Next.js (App Router) | 16.2.10 |
| | React | 19.2.4 |
| | TypeScript | 5.x |
| | Tailwind CSS | 4.x |
| **Backend** | Python | 3.11+ |
| | FastAPI | 0.115.12 |
| | SQLAlchemy | 2.0.41 |
| | Uvicorn | 0.34.2 |
| **Database** | PostgreSQL | 14+ |
| **AI/ML** | Ultralytics YOLO | 8.3.163 |
| | OpenCV | 4.12.0.88 |
| | Pillow | 11.3.0 |
| | PyTorch (CUDA) | Latest |
| **Auth** | JWT (PyJWT) | 2.10.1 |
| | PBKDF2-HMAC-SHA256 | — |
| | SMTP (Gmail OTP) | — |

---

## Tính năng chính

### Nhận diện thời gian thực (Realtime)
- Kết nối webcam qua **WebSocket** — hiển thị kết quả nhận diện ngay lập tức
- **Centroid Tracking + Character Voting**: theo dõi biển số qua các frame, vote ký tự để tăng độ chính xác
- **Snapshot frame đầu tiên**: khi track finalize, hệ thống dùng frame đầu tiên của track làm ảnh verification
- **Confidence từ voting**: độ tin cậy được tính bằng Geometric Mean từ character voting khi track finalize
- Tự động lưu kết quả vào database khi biển số biến mất (track finalize)

### Nhận diện từ ảnh
- Upload ảnh (JPG, PNG, BMP, WebP) để nhận diện
- Hiển thị bounding box, text và confidence score
- Lưu kết quả vào lịch sử

### Nhận diện từ video
- Upload video (MP4, AVI, MOV, MKV) — xử lý nền (background thread)
- **Centroid Tracking + Character Voting** cho video (xử lý ~2 FPS)
- Snapshot video dùng frame đầu tiên của track làm ảnh verification
- Theo dõi tiến trình xử lý real-time qua polling
- Tải video kết quả đã annotate

### Quản lý người dùng & Xác thực
- Đăng ký独立 tại `/signin`, đăng nhập tại `/login`
- **Xác thực OTP qua Gmail** (SMTP đã cấu hình sẵn)
- Chế độ Development: OTP in ra console khi SMTP chưa khả dụng
- Phân quyền Admin / User
- Quên mật khẩu → OTP → Đặt lại mật khẩu (mật khẩu mới không được trùng mật khẩu cũ)

### Phân vùng camera (Region)
- Xem danh sách phân vùng camera
- Gán region khi nhận diện để thống kê theo khu vực

### Dashboard quản trị (Admin)
- Thống kê tổng quan: tổng lần nhận diện, người dùng, phân vùng, video
- Biểu đồ nhận diện theo ngày (7 ngày gần nhất)
- Biểu đồ tỷ lệ theo loại nguồn (camera / ảnh / video)
- Thống kê biến thiên confidence theo khu vực
- Quản lý người dùng (tạo, sửa role, kích hoạt/vô hiệu hóa, xóa)
- Xác minh kết quả nhận diện: nút **Đúng** / **Sai** / **Xóa** (xóa detection khỏi database)
- Nhật ký hoạt động (hiển thị email người thực hiện)

### Lịch sử nhận diện
- Xem lịch sử nhận diện với bộ lọc theo biển số, nguồn, thời gian, khu vực
- Xem chi tiết snapshot với bounding box
- Phân trang

---

## Cấu trúc thư mục

```
vietnamlicenseplate/
├── package.json                    # Root: concurrently chạy backend + frontend
├── .gitignore
├── README.md
│
├── backend/                        # Backend Python (FastAPI)
│   ├── .env                        # Cấu hình môi trường (DB, SMTP)
│   ├── .env.example                # Mẫu file cấu hình
│   ├── requirements.txt            # Danh sách thư viện Python
│   ├── weights/                    # Model YOLOv8 (không commit vào git)
│   │   ├── stage1_detector_robust.pt
│   │   ├── stage2_char_detector.pt
│   │   └── stage3_char_classify.pt
│   ├── static/snapshots/           # Ảnh snapshot nhận diện (UUID.jpg)
│   └── src/
│       ├── main.py                 # Entry point — FastAPI app, lifespan, CORS
│       ├── config/
│       │   ├── settings.py         # Cấu hình hệ thống (thresholds, DB, SMTP)
│       │   └── database.py         # SQLAlchemy engine, session, Base
│       ├── models/
│       │   ├── models.py           # 8 ORM models
│       │   └── schemas.py          # Pydantic schemas (request/response)
│       ├── routes/
│       │   ├── auth.py             # /auth/* — đăng ký, đăng nhập, OTP
│       │   ├── predict.py          # /predict-*, /tasks/*, /ws/lpr
│       │   ├── admin.py            # /admin/* — dashboard, thống kê
│       │   ├── regions.py          # /regions — danh sách phân vùng
│       │   └── history.py          # /history — lịch sử nhận diện
│       ├── controllers/
│       │   ├── auth_controller.py
│       │   ├── predict_controller.py
│       │   ├── admin_controller.py
│       │   ├── region_controller.py
│       │   └── history_controller.py
│       ├── services/
│       │   ├── ai_pipeline.py      # LPRPipeline class — YOLOv8 3-stage
│       │   ├── preprocessing.py    # Deskew, threshold, filter, pad
│       │   ├── validation.py       # Validate format biển số VN
│       │   ├── tracking.py         # CentroidTracker + Character Voting
│       │   ├── predict_service.py  # Xử lý ảnh/video/WebSocket
│       │   ├── auth_service.py     # Xác thực, JWT, OTP, phân quyền
│       │   ├── admin_service.py    # Thống kê, quản lý user/region
│       │   ├── region_service.py   # Truy vấn region
│       │   └── history_service.py  # Truy vấn lịch sử
│       └── utils/
│           ├── security.py         # PBKDF2 password hashing
│           ├── email.py            # Gửi email OTP qua SMTP Gmail
│           └── helpers.py          # Snapshot, file cleanup, activity log
│
├── frontend/                       # Frontend Next.js (App Router)
│   ├── package.json
│   ├── next.config.ts              # Rewrites proxy → backend
│   └── src/
│       ├── app/
│       │   ├── layout.tsx          # Root layout (font, globals.css)
│       │   ├── page.tsx            # Root → redirect /login
│       │   ├── login/page.tsx      # Trang đăng nhập standalone
│       │   ├── signin/page.tsx     # Trang đăng ký独立 (embedded LoginModal)
│       │   ├── home/page.tsx       # Trang chủ — Tab Image/Video/Realtime
│       │   └── admin/              # 7 trang quản trị
│       │       ├── layout.tsx      # Layout admin (Sidebar + TopBar)
│       │       ├── dashboard/
│       │       ├── users/
│       │       ├── verification/
│       │       ├── search/
│       │       ├── activity-log/
│       │       ├── prediction-ratio/
│       │       └── variable-stats/
│       ├── components/
│       │   ├── Navbar.tsx          # Thanh điều hướng chính
│       │   ├── LoginModal.tsx      # Modal 5 chế độ (login/register/OTP/forgot/reset)
                                      # Hỗ trợ embedded mode cho /signin
│       │   ├── AnimatedBackground.tsx # Hiệu ứng nền animation
│       │   ├── ImageTab.tsx        # Tab nhận diện ảnh
│       │   ├── VideoTab.tsx        # Tab nhận diện video
│       │   ├── RealtimeTab.tsx     # Tab nhận diện thời gian thực
│       │   ├── SnapshotModal.tsx   # Modal xem snapshot
│       │   ├── GeneralHistoryModal.tsx
│       │   └── admin/
│       │       ├── Sidebar.tsx
│       │       └── TopBar.tsx
│       ├── hooks/
│       │   └── useWebSocket.ts     # Hook WebSocket kết nối backend
│       ├── lib/
│       │   ├── api.ts             # API_BASE, BACKEND_URL, WS_URL
│       │   └── utils.ts           # parseVnDatetime, formatVnTime
│       └── styles/
│           └── admin.css
```

---

## Yêu cầu hệ thống

| Phần mềm | Phiên bản tối thiểu | Ghi chú |
|---|---|---|
| **Python** | 3.11+ | `python --version` |
| **Node.js** | 18+ | `node --version` |
| **PostgreSQL** | 14+ | Chạy sẵn trước khi start backend |
| **Git** | 2.x+ | Clone repository |

**GPU (khuyến nghị):**
- CUDA 11.8+ và cuDNN 8.6+
- GPU NVIDIA tương thích (RTX series trở lên)
- Hệ thống tự động fallback về CPU nếu không có GPU

---

## Hướng dẫn cài đặt

### 1. Clone repository

```bash
git clone https://github.com/<your-username>/vietnamlicenseplate.git
cd vietnamlicenseplate
```

### 2. Cài đặt Backend

```bash
cd backend

# Tạo và kích hoạt virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
```

### 3. Chuẩn bị file Weights (Model AI)

Tạo thư mục `weights/` trong thư mục `backend/` và đặt 3 file model YOLOv8:

```
backend/weights/
├── stage1_detector_robust.pt    # Mô hình phát hiện biển số
├── stage2_char_detector.pt      # Mô hình phát hiện ký tự
└── stage3_char_classify.pt      # Mô hình phân loại ký tự
```

> **Lưu ý**: Hệ thống sẽ báo lỗi và không khởi động nếu thiếu bất kỳ file weights nào.

### 4. Cấu hình file `.env` (Backend)

```bash
cp .env.example .env
```

Chỉnh sửa file `.env` theo hướng dẫn chi tiết ở mục [Cấu hình môi trường](#cấu-hình-môi-trường) bên dưới.

### 5. Cài đặt Frontend

```bash
cd ../frontend
npm install
```

---

## Cấu hình môi trường

### Backend — `backend/.env`

```env
# ===== Database PostgreSQL =====
DATABASE_URL=postgresql://postgres:password@localhost:5432/Web_orc

# ===== SMTP Configuration (Gmail) =====
# SMTP đã cấu hình sẵn — OTP gửi về email thật
SMTP_USER=vietc3k49@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

> **Lưu ý**: `SMTP_PASSWORD` là App Password (16 ký tự), **KHÔNG PHẢI** mật khẩu Gmail thông thường.
> Nếu muốn dùng email khác, thay `SMTP_USER` và tạo App Password mới.

#### Hướng dẫn cấu hình SMTP Gmail

Hệ thống sử dụng SMTP Gmail để gửi mã OTP xác thực. Thực hiện theo các bước sau:

1. **Đăng nhập** tài khoản Gmail trên trình duyệt
2. Vào **App Passwords**: https://myaccount.google.com/apppasswords
3. Chọn **Create app password**:
   - App name: `Vietnam LPR` (tùy ý)
   - Nhấn **Create**
4. **Copy mật khẩu ứng dụng** (16 ký tự, ví dụ: `abcd efgh ijkl mnop`)
5. Paste vào `SMTP_PASSWORD` trong file `.env`

> **Lưu ý**: Nếu chưa cấu hình SMTP, hệ thống vẫn hoạt động bình thường ở chế độ Development — mã OTP sẽ được in ra console (terminal) thay vì gửi email. Toàn bộ luồng đăng ký → xác thực OTP → đăng nhập vẫn hoạt động để test.

#### Confidence Thresholds (tùy chọn)

```env
# Nhận diện ảnh
# CONF_S1_IMG=0.6    # Stage 1: Phát hiện biển số
# CONF_S2_IMG=0.5    # Stage 2: Phát hiện ký tự
# CONF_S3_IMG=0.3    # Stage 3: Phân loại ký tự

# Nhận diện video
# CONF_S1_VID=0.5
# CONF_S2_VID=0.8
# CONF_S3_VID=0.7
```

### Frontend — `frontend/.env.local` (tùy chọn)

```env
# URL backend trực tiếp (dùng cho upload file lớn, vượt qua proxy 10MB của Next.js)
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000/api/v1

# URL WebSocket (Next.js rewrites KHÔNG hỗ trợ WebSocket)
NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000/api/v1/ws/lpr
```

> Nếu không tạo file `.env.local`, hệ thống sẽ dùng giá trị mặc định là `http://127.0.0.1:8000`.

---

## Chạy ứng dụng

### Khởi chạy Backend

```bash
cd backend
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

python -m src.main
```

Backend chạy tại: **http://127.0.0.1:8000**
Swagger UI: **http://127.0.0.1:8000/docs**

### Khởi chạy Frontend

```bash
cd frontend
npm run dev
```

Frontend chạy tại: **http://localhost:3000**

### Chạy cả hai cùng lúc

```bash
# Từ thư mục gốc
npm run dev
```

### Truy cập ứng dụng

| Trang | URL | Ghi chú |
|---|---|---|
| Mặc định | http://localhost:3000 | Tự redirect → `/login` |
| Đăng nhập | http://localhost:3000/login | Form đăng nhập |
| Đăng ký | http://localhost:3000/signin | Form đăng ký独立, gửi OTP qua Gmail |
| Trang chủ | http://localhost:3000/home | Realtime webcam, Image, Video |
| Khu vực Admin | http://localhost:3000/admin | Cần đăng nhập với role `admin` |

---

## API Endpoints

Tất cả API nằm dưới tiền tố `/api/v1`.

### Xác thực (`/api/v1/auth`)

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/auth/register` | Đăng ký tài khoản → gửi OTP qua Gmail |
| POST | `/auth/verify-otp` | Xác thực OTP kích hoạt tài khoản |
| POST | `/auth/login` | Đăng nhập (cần tài khoản đã xác thực OTP) |
| POST | `/auth/forgot-password` | Gửi OTP khôi phục mật khẩu |
| POST | `/auth/reset-password` | Đặt lại mật khẩu bằng OTP (mật khẩu mới ≠ cũ) |
| POST | `/auth/logout` | Đăng xuất |
| GET | `/auth/test-email` | Test kết nối SMTP Gmail |

### Nhận diện (`/api/v1`)

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/predict-image` | Upload ảnh để nhận diện |
| POST | `/predict-video` | Upload video để nhận diện (xử lý nền) |
| GET | `/tasks/{task_id}` | Kiểm tra tiến trình video |
| GET | `/tasks/{task_id}/download` | Tải video kết quả |
| WS | `/ws/lpr` | WebSocket nhận diện thời gian thực |

### Quản trị (`/api/v1/admin`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/admin/stats` | Thống kê tổng quan |
| GET | `/admin/users` | Danh sách người dùng |
| POST | `/admin/users` | Tạo tài khoản mới |
| PUT | `/admin/users/{user_id}/role` | Cập nhật role người dùng |
| POST | `/admin/users/{user_id}/toggle-active` | Kích hoạt / vô hiệu hóa tài khoản |
| DELETE | `/admin/users/{user_id}` | Xóa người dùng |
| GET | `/admin/detections/unverified` | Danh sách chưa xác minh |
| POST | `/admin/verify-detection` | Xác minh kết quả nhận diện (đúng/sai) |
| DELETE | `/admin/detections/{detection_id}` | Xóa bản ghi nhận diện |
| GET | `/admin/detections/search` | Tìm kiếm detections |
| GET | `/admin/regions-stats` | Thống kê theo khu vực |
| GET | `/admin/activity-logs` | Nhật ký hoạt động |

### Phân vùng (`/api/v1`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/regions` | Danh sách phân vùng camera |

### Lịch sử (`/api/v1`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/history` | Lịch sử nhận diện (hỗ trợ filter & pagination) |
| DELETE | `/history/{detection_id}` | Xóa bản ghi nhận diện |

---

## AI Pipeline

Hệ thống sử dụng kiến trúc **3 giai đoạn (3-Stage Pipeline)** dựa trên YOLOv8:

```
Ảnh đầu vào
    │
    ▼
┌──────────────────────────────────┐
│  STAGE 1: Plate Detection        │  YOLOv8 Object Detection
│  Model: stage1_detector_robust   │  Input: ảnh gốc (1280px)
│  NMS: IoU threshold = 0.5        │  Confidence: 0.6 (ảnh) / 0.5 (video)
└──────────────┬───────────────────┘
               │ Cắt từng biển số
               ▼
┌──────────────────────────────────┐
│  Deskew + Pad + Preprocess       │
│  - OTSU → minAreaRect → xoay    │
│  - Pad +8px                      │
│  - Grayscale, sharpen            │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  STAGE 2: Character Detection    │  YOLOv8 Object Detection
│  Model: stage2_char_detector     │  Input: ảnh biển số (640px)
│  NMS: IoU threshold = 0.3        │  Confidence: 0.5 / 0.8
│  + Filter box nhỏ < 40% avg      │
│  + Sắp xếp theo hàng (Y-gap)    │
└──────────────┬───────────────────┘
               │ Cắt từng ký tự → Resize 64×64
               ▼
┌──────────────────────────────────┐
│  STAGE 3: Character Classification │  YOLOv8 Classification
│  Model: stage3_char_classify     │  Input: ảnh ký tự 64×64
│  - Phân loại trên ảnh GỐC       │  Confidence: 0.3 / 0.7
│  - Lấy alternatives cho format  │
│    correction                   │
└──────────────┬───────────────────┘
               │ Validate format VN
               │ Ghép chuỗi theo thứ tự
               ▼
         Kết quả: "51A-12345"
```

### Centroid Tracking + Character Voting (Video & Realtime)

```
Frame N:   Detect "51A-12345" bbox=[100,200,350,280]
Frame N+1: Detect "51A-12345" bbox=[102,201,352,281]  ← match (IOU + centroid + text)
Frame N+2: Không detect được                            ← miss_count = 1
Frame N+3: Không detect được                            ← miss_count = 2
Frame N+4: Không detect được                            ← miss_count = 3
Frame N+5: Không detect được                            ← miss_count = 4 → FINALIZE
           │
           ▼
Character Voting (từng vị trí ký tự):
  Vị trí 0: '5'×5, 'S'×1  → '5' (đa số)
  Vị trí 1: '1'×6          → '1' (đồng nhất)
  ...
  Kết quả final: "51A-12345" (confidence từ Geometric Mean)
```

**Matching criteria**: Detection match track bằng combined score = IOU×40% + TextSimilarity×40% + CentroidSimilarity×20%. **BẮT BUỘC** text similarity ≥ 0.5 nếu không sẽ tạo track mới.

**Finalized buffer**: Chống trùng lặp — nếu detection match với track vừa finalize trong 5s → skip.

**Merge buffer**: Gộp các track cùng text hoặc fuzzy match (edit_distance ≤ 1, gap ≤ 2s) → combine votes, giữ frame đầu tiên cũ nhất.

### Snapshot Frame Đầu Tiên (Verification)

Khi track finalize (biển số biến mất), hệ thống dùng **frame đầu tiên** của track làm ảnh snapshot verification:

```
Frame 1: "29A12345" conf=0.72 → lưu frame này làm snapshot verification
Frame 2: "29A12345" conf=0.89 → cập nhật votes
Frame 3: "29A12345" conf=0.91 → cập nhật votes
Frame 4-11: conf giảm dần → giữ votes
Frame 12: Biển biến mất → finalize
  → Snapshot: dùng frame 1 (ảnh đầu tiên khi biển xuất hiện)
  → Confidence: Geometric Mean từ character voting qua tất cả frame
```

→ Ảnh snapshot là frame đầu tiên khi biển số xuất hiện, giúp admin thấy rõ biển số ở thời điểm ban đầu.

### Database Tables

| Table | Mô tả |
|---|---|
| `users` | Tài khoản người dùng (username, email, password_hash, role, is_verified) |
| `detections` | Kết quả nhận diện (plate_text, plate_confidence, alt_text, alt_confidence, total_frames, frame_start, frame_end, image_path, source_type, region_id, video_job_id) |
| `predictions` | Xác minh kết quả (is_correct, verified_by) |
| `regions` | Phân vùng camera (name, location, is_active) |
| `video_jobs` | Tiến trình xử lý video (status, progress, current_frame, total_frames, fps, duration, output_video, output_csv, output_xlsx) |
| `statistics` | Thống kê theo ngày (total_detections, avg_confidence, correct/incorrect) |
| `tokens` | Mã OTP (token, type: email_verify/password_reset, expires_at) |
| `activity_logs` | Nhật ký hoạt động (action, detail, ip_address) |

---

## Các kỹ thuật xử lý

| Kỹ thuật | Mô tả | Vị trí |
|---|---|---|
| **NMS Stage 1** | Loại bỏ box trùng lặp phát hiện biển số (IoU > 0.5) | `ai_pipeline.py` |
| **NMS Stage 2** | Loại bỏ box trùng lặp ký tự (IoU > 0.3) | `ai_pipeline.py` |
| **Deskew** | Xoay ảnh biển số về phương ngang (giới hạn ±45°) | `preprocessing.py` |
| **Plate Padding** | Thêm 8px padding trước khi detect ký tự | `preprocessing.py` |
| **Filter Small Boxes** | Bỏ box có diện tích < 40% trung bình | `preprocessing.py` |
| **Character Classification** | Stage3 phân loại ký tự trên ảnh 64×64, có alternatives cho format correction | `ai_pipeline.py` |
| **Character Sorting** | Tách 2 dòng theo Y-gap, sort trái→phải mỗi dòng | `ai_pipeline.py` |
| **Plate Validation** | Validate format biển số VN (8-10 ký tự, chữ hợp lệ) | `validation.py` |
| **Format Correction** | Sửa ký tự sai dựa trên vị trí trên biển VN (pos0-1=số, pos2=chữ, pos4+=số) | `ai_pipeline.py` |
| **Centroid Tracking** | Theo dõi centroid detection qua frame (IOU + centroid + text similarity) | `tracking.py` |
| **Character Voting** | Majority vote từng vị trí ký tự qua nhiều frame | `tracking.py` |
| **First Frame Snapshot** | Dùng frame đầu tiên của track làm ảnh snapshot verification | `tracking.py` |
| **Frame Skip** | Video xử lý ~2 FPS (mỗi frame ~0.5s) để tăng tốc | `predict_service.py` |
| **Miss Threshold** | 4 frame mất tín hiệu liên tiếp → finalize track (~2s ở 2 FPS) | `tracking.py` |

---

## Tài khoản mặc định

Sau khi chạy backend lần đầu, hệ thống tự động tạo:

- **4 phân vùng camera mặc định**: Camera Cổng Chính, Cổng Phụ, Hầm Gửi Xe A, Hầm Gửi Xe B
- **Tài khoản admin mặc định**: `abc1` / `123456` (bypass qua DB, không cần đăng ký)

Tài khoản user cần được tạo qua API `/auth/register` và xác thực OTP trước khi đăng nhập.

---

## Ghi chú phát triển

- Frontend dùng **Next.js rewrites** để proxy API `/api/v1/*` → backend `http://127.0.0.1:8000`. Tuy nhiên, **WebSocket** và **upload file lớn (>10MB)** cần kết nối trực tiếp tới backend.
- Backend chạy **UVicorn** với `reload=True` ở chế độ development.
- Database tables tự động tạo khi khởi động (`Base.metadata.create_all`).
- File snapshot ảnh được lưu trong thư mục `static/snapshots/` của backend.
- Hệ thống tự động detect GPU (CUDA) và fallback về CPU nếu không khả dụng.
- Root `package.json` dùng `concurrently` để chạy backend + frontend cùng lúc.

---

## License

Dự án © 2026 — Hệ thống Nhận diện Biển số xe Việt Nam. Công nghệ YOLOv8 Object Detection & Classification.
