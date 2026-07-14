# Vietnam License Plate Recognition (LPR)

> Hệ thống nhận diện biển số xe Việt Nam sử dụng trí tuệ nhân tạo — tích hợp nhận diện thời gian thực qua webcam, nhận diện từ ảnh và video, quản lý người dùng, phân vùng camera, cùng bảng điều khiển quản trị toàn diện.

---

## Mục lục

- [Giới thiệu](#giới-thiệu)
- [Ảnh chụp giao diện](#ảnh-chụp-giao-diện)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Hướng dẫn cài đặt từng bước](#hướng-dẫn-cài-đặt-từng-bước)
  - [Bước 1: Clone repository](#bước-1-clone-repository)
  - [Bước 2: Cài đặt PostgreSQL](#bước-2-cài-đặt-postgresql)
  - [Bước 3: Setup Backend (Python)](#bước-3-setup-backend-python)
  - [Bước 4: Setup Frontend (Next.js)](#bước-4-setup-frontend-nextjs)
  - [Bước 5: Chạy ứng dụng](#bước-5-chạy-ứng-dụng)
- [Cấu hình môi trường chi tiết](#cấu-hình-môi-trường-chi-tiết)
  - [Backend — `backend/.env`](#backend--backendenv)
  - [Frontend — `frontend/.env.local`](#frontend--frontendenvlocal)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Cơ sở dữ liệu (Database Schema)](#cơ-sở-dữ-liệu-database-schema)
- [API Endpoints](#api-endpoints)
- [AI Pipeline](#ai-pipeline)
- [Các kỹ thuật xử lý](#các-kỹ-thuật-xử-lý)
- [Tính năng chính](#tính-năng-chính)
- [Tài khoản mặc định](#tài-khoản-mặc-định)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Troubleshooting — Lỗi thường gặp](#troubleshooting--lỗi-thường-gặp)
- [Ghi chú phát triển](#ghi-chú-phát-triển)
- [License](#license)

---

## Giới thiệu

**Vietnam LPR** là ứng dụng web fullstack giúp nhận diện tự động biển số xe Việt Nam từ nhiều nguồn khác nhau: webcam thời gian thực, ảnh tĩnh và video.

Hệ thống sử dụng kiến trúc **3 giai đoạn YOLOv8**:

1. **Stage 1** — Phát hiện vị trí biển số trong ảnh
2. **Stage 2** — Phát hiện từng ký tự trên biển số
3. **Stage 3** — Phân loại ký tự (số, chữ)

Kết hợp **Centroid Tracking + Character Voting** để theo dõi biển số qua nhiều frame và bỏ phiếu ký tự, tăng độ chính xác đáng kể so với nhận diện từng frame đơn lẻ.

**Điểm nổi bật:**

- Nhận diện thời gian thực qua webcam (WebSocket)
- MJPEG Live Camera — xem camera IP trực tiếp từ trình duyệt
- Upload ảnh / video để nhận diện
- Bảng quản trị (Admin Dashboard) với thống kê, biểu đồ, xác minh kết quả
- Hệ thống tự động dọn dẹp dữ liệu cũ sau 7 ngày
- Lưu ảnh snapshot lên Cloudinary (cloud) hoặc local

---

## Ảnh chụp giao diện

### Trang đăng nhập (Waze Theme)

```
┌─────────────────────────────────────────────┐
│                                             │
│          🚗  Vietnam LPR                    │
│                                             │
│     ┌───────────────────────────────┐       │
│     │  Username: [______________]   │       │
│     │  Password: [______________]   │       │
│     │                               │       │
│     │       [ 🔑 Đăng nhập ]        │       │
│     │                               │       │
│     │  Quên mật khẩu? | Đăng ký     │       │
│     └───────────────────────────────┘       │
│                                             │
└─────────────────────────────────────────────┘
```

### Trang chủ — 4 Tab

```
┌──────────────────────────────────────────────────────────┐
│  🚗 Vietnam LPR    [ Image ] [ Video ] [ Realtime ] [📷] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │                                                    │  │
│  │              Vùng hiển thị nhận diện               │  │
│  │           (ảnh + bbox + plate text)                │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Plate: 51A-12345  |  Confidence: 92.3%                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Admin Dashboard

```
┌──────────────────────────────────────────────────────────┐
│ ☰ Dashboard    │  Tổng quan                             │
│ 👥 Users       │  ┌────────┐ ┌────────┐ ┌────────┐     │
│ ✅ Verify      │  │1,234   │ │  5     │ │  89%   │     │
│ 🔍 Search      │  │Detections│ │ Users │ │Accuracy│     │
│ 📊 Prediction  │  └────────┘ └────────┘ └────────┘     │
│ 📈 Stats       │                                         │
│ 📋 Activity    │  [Biểu đồ detections theo ngày]        │
│ 📹 Cameras     │  [Biểu đồ confidence distribution]     │
│                │  [Top plates + Drill-down]              │
└──────────────────────────────────────────────────────────┘
```

---

## Yêu cầu hệ thống

Trước khi bắt đầu, bạn cần cài đặt các phần mềm sau trên máy tính:

### Bắt buộc

| Phần mềm | Phiên bản tối thiểu | Cách kiểm tra | Ghi chú |
|---|---|---|---|
| **Python** | 3.11+ | Mở terminal, gõ `python --version` | Nếu chưa có, tải từ [python.org](https://www.python.org/downloads/) |
| **Node.js** | 18+ | Mở terminal, gõ `node --version` | Nếu chưa có, tải từ [nodejs.org](https://nodejs.org/) (phiên bản LTS) |
| **PostgreSQL** | 14+ | Mở terminal, gõ `psql --version` | Nếu chưa có, xem [Bước 2](#bước-2-cài-đặt-postgresql) |
| **Git** | 2.x+ | Mở terminal, gõ `git --version` | Nếu chưa có, tải từ [git-scm.com](https://git-scm.com/) |

### Khuyến nghị (tùy chọn)

| Phần mềm | Phiên bản | Ghi chú |
|---|---|---|
| **GPU NVIDIA** | RTX series trở lên | CUDA 11.8+ và cuDNN 8.6+ để tăng tốc AI |
| **CUDA Toolkit** | 11.8+ | Tải từ [nvidia.com](https://developer.nvidia.com/cuda-toolkit) |
| **pgAdmin** | 4.x | GUI quản lý PostgreSQL, tiện cho newbie |

> **Lưu ý:** Hệ thống tự động detect GPU và fallback về CPU nếu không có. Chạy CPU sẽ chậm hơn nhưng vẫn hoạt động bình thường.

---

## Hướng dẫn cài đặt từng bước

> **Nguyên tắc:** Làm tuần tự từ Bước 1 → Bước 5. Nếu gặp lỗi, xem section [Troubleshooting](#troubleshooting--lỗi-thường-gặp) ở cuối file.

---

### Bước 1: Clone repository

Mở **Terminal** (Windows: PowerShell hoặc Git Bash; macOS/Linux: Terminal):

```bash
# Vào thư mục muốn lưu dự án (ví dụ: Desktop)
cd ~/Desktop

# Clone repository
git clone https://github.com/PhungHieu2k3/vietnamlicenseplate.git

# Vào thư mục dự án
cd vietnamlicenseplate
```

Sau bước này, cấu trúc thư mục sẽ như sau:

```
vietnamlicenseplate/
├── README.md              ← Bạn đang đọc file này
├── package.json           ← Root: chạy backend + frontend cùng lúc
├── backend/               ← Backend Python (FastAPI)
├── frontend/              ← Frontend Next.js
└── docs/                  ← Tài liệu thiết kế
```

---

### Bước 2: Cài đặt PostgreSQL

> **Bỏ qua bước này** nếu bạn đã có PostgreSQL 14+ chạy trên máy.

#### 2.1. Tải và cài đặt PostgreSQL

**Windows:**
1. Truy cập https://www.postgresql.org/download/windows/
2. Tải installer (PostgreSQL 16 recommended)
3. Chạy installer, nhấn **Next** qua các bước:
   - Thư mục cài đặt: giữ mặc định
   - Chọn component: giữ tất cả (PostgreSQL Server, pgAdmin, Command Line Tools)
   - **Port**: giữ mặc định `5432`
   - **Password**: đặt mật khẩu cho postgres user (**ghi nhớ mật khẩu này!**)
     - Ví dụ: `postgres` (đơn giản cho development)
   - **Port**: giữ `5432`
   - Nhấn **Next** → **Install**

**macOS:**
```bash
# Dùng Homebrew
brew install postgresql@16
brew services start postgresql@16
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### 2.2. Tạo database

Mở terminal và chạy:

```bash
# Đăng nhập vào PostgreSQL
# Windows (nếu dùng installer): mở "SQL Shell (psql)" từ Start Menu
# macOS/Linux:
psql -U postgres
```

Nhập mật khẩu postgres khi được yêu cầu, rồi chạy các lệnh SQL sau:

```sql
-- Tạo database tên "Web_orc"
CREATE DATABASE "Web_orc";

-- Kiểm tra đã tạo thành công
\l

-- Thoát khỏi psql
\q
```

> **Lưu ý:** Tên database PHẢI là `Web_orc` (có chữ hoa W, chữ thường e, gạch dưới, chữ hoa O, chữ thường r, chữ hoa c). Nếu muốn đặt tên khác, bạn phải thay đổi trong file `.env` ở Bước 3.

#### 2.3. Verify PostgreSQL hoạt động

```bash
# Kết nối lại để kiểm tra
psql -U postgres -d "Web_orc"

# Nếu không có lỗi → OK!
\q
```

---

### Bước 3: Setup Backend (Python)

#### 3.1. Vào thư mục backend

```bash
cd backend
```

#### 3.2. Tạo Virtual Environment

Virtual Environment (venv) giúp cô lập thư viện Python của dự án này với các dự án khác trên máy.

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

> **Dấu hiệu thành công:** Đầu dòng terminal xuất hiện `(venv)`, ví dụ: `(venv) C:\Users\You\backend>`

> **Nếu gặp lỗi `python` không tìm thấy:** Thử dùng `python3` thay thế. Nếu vẫn lỗi, xem [Troubleshooting](#lỗi-python-không-tìm-thấy).

#### 3.3. Cài đặt thư viện Python

```bash
pip install -r requirements.txt
```

Danh sách thư viện sẽ được cài đặt:

| Thư viện | Phiên bản | Mục đích |
|---|---|---|
| `fastapi` | ≥0.100.0 | Web framework chính |
| `uvicorn` | ≥0.22.0 | ASGI server (chạy FastAPI) |
| `python-multipart` | ≥0.0.6 | Xử lý file upload |
| `numpy` | latest | Xử lý số học |
| `opencv-python-headless` | latest | Xử lý ảnh (OpenCV) |
| `ultralytics` | latest | YOLOv8 framework |
| `torch` + `torchvision` | latest | PyTorch (AI engine) |
| `pydantic` | ≥2.0 | Validation dữ liệu |
| `pydantic-settings` | latest | Đọc biến môi trường |
| `sqlalchemy` | latest | ORM (Object-Relational Mapping) |
| `psycopg2-binary` | latest | PostgreSQL driver |
| `cloudinary` | latest | Upload ảnh lên cloud |

> **Lưu ý:** Thư viện `torch` có thể nặng ~2GB. Nếu máy có NVIDIA GPU, hệ thống sẽ cài phiên bản CUDA. Nếu không, sẽ cài phiên bản CPU.

> **Thời gian cài đặt:** ~5-15 phút tùy tốc độ mạng và máy tính.

#### 3.4. Chuẩn bị file Weights (Model AI)

Hệ thống cần 3 file model YOLOv8 để chạy AI pipeline. Tạo thư mục `weights` trong `backend/`:

```bash
# Từ thư mục backend/
mkdir weights
```

```
backend/weights/
├── stage1_detector_robust.pt    (~17.5 MB) — Mô hình phát hiện biển số
├── stage2_char_detector.pt      (~23.4 MB) — Mô hình phát hiện ký tự
└── stage3_char_classify.pt      (~12.2 MB) — Mô hình phân loại ký tự
```

> **Quan trọng:** Bạn cần liên hệ người quản lý dự án hoặc download từ nguồn chia sẻ của nhóm để lấy 3 file `.pt` này. Hệ thống sẽ **báo lỗi và không khởi động** nếu thiếu bất kỳ file nào.

> **Ngoài ra**, thư mục `weights/` nằm trong `.gitignore` nên không được commit lên git — đây là deliberate design để giữ repo nhẹ.

#### 3.5. Tạo file cấu hình môi trường `.env`

```bash
# Từ thư mục backend/
cp .env.example .env
```

Mở file `.env` bằng editor yêu thích và chỉnh sửa:

**Windows (Notepad++):**
```bash
notepad++ .env
```

**Windows (VS Code):**
```bash
code .env
```

**macOS/Linux:**
```bash
nano .env
# hoặc
code .env
```

Nội dung file `.env`:

```env
# ===== Database PostgreSQL =====
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/Web_orc

# ===== SMTP Configuration (Gmail) =====
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# ===== Cloudinary (Lưu trữ ảnh snapshot trên cloud) =====
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
CLOUDINARY_FOLDER=anpr-snapshots
```

**Thay đổi từng dòng:**

| Dòng | Thay thế bằng | Ví dụ |
|---|---|---|
| `YOUR_PASSWORD` | Mật khẩu PostgreSQL bạn đặt ở Bước 2 | `postgres` |
| `your-email@gmail.com` | Địa chỉ Gmail của bạn | `abc@gmail.com` |
| `your-16-char-app-password` | App Password (16 chữ, xem Bước 3.6) | `abcdefghijklmnop` |
| `api_key:api_secret@cloud_name` | Thông tin Cloudinary (xem Bước 3.7) | `123456789:abcdef@mycloud` |

> **Lưu ý về Cloudinary:** Nếu bạn chưa muốn cấu hình Cloudinary, hãy để trống `CLOUDINARY_URL=""`. Hệ thống sẽ tự động fallback về lưu ảnh local trong thư mục `static/snapshots/`.

Xem chi tiết từng biến ở section [Cấu hình môi trường](#cấu-hình-môi-trường-chi-tiết).

#### 3.6. Hướng dẫn tạo Gmail App Password (SMTP)

Hệ thống sử dụng SMTP Gmail để gửi mã OTP xác thực khi đăng ký/đăng nhập.

> **Nếu chưa cấu hình SMTP:** Hệ thống vẫn hoạt động — mã OTP sẽ in ra **console (terminal)** thay vì gửi email. Toàn bộ luồng đăng ký → OTP → đăng nhập vẫn chạy được để test.

**Các bước tạo App Password:**

1. **Đăng nhập** tài khoản Gmail trên trình duyệt web
2. Vào trang **App Passwords**: https://myaccount.google.com/apppasswords
   - Nếu thấy yêu cầu "2-Step Verification", bạn phải **bật 2FA** trước:
     - Vào https://myaccount.google.com/signinoptions/two-step-verification
     - Làm theo hướng dẫn (thường dùng số điện thoại)
     - Sau khi bật xong, quay lại link App Passwords
3. Chọn **Create app password**:
   - App name: nhập `Vietnam LPR` (tùy ý, nhớ được là OK)
   - Nhấn **Create**
4. **Copy mật khẩu ứng dụng** (16 ký tự, dạng: `abcd efgh ijkl mnop`)
5. Paste vào `SMTP_PASSWORD` trong file `.env`

> **Lưu ý quan trọng:**
> - App Password **KHÔNG PHẢI** mật khẩu Gmail thông thường
> - App Password chỉ hiển thị **một lần** khi tạo — copy ngay lập tức
> - Nếu mất, tạo lại App Password mới

#### 3.7. Hướng dẫn cấu hình Cloudinary (tùy chọn)

Cloudinary dùng để lưu trữ ảnh snapshot lên cloud, giúp quản trị viên xem ảnh verification từ bất kỳ đâu.

**Nếu không cấu hình Cloudinary:** Ảnh sẽ lưu local trong `backend/static/snapshots/`. Vẫn hoạt động bình thường nhưng ảnh chỉ xem được trên máy chủ.

**Các bước cấu hình:**

1. Đăng ký tài khoản miễn phí tại https://cloudinary.com/users/register/free
2. Sau đăng ký, vào **Dashboard** → bạn sẽ thấy:
   - **Cloud Name**: ví dụ `mycloud123`
   - **API Key**: ví dụ `123456789012345`
   - **API Secret**: ví dụ `abcdefghijklmnopqrstuvwx`
3. Tạo folder `anpr-snapshots` trong Media Library (hoặc để Cloudinary tự tạo)
4. Điền vào file `.env`:

```env
CLOUDINARY_URL=cloudinary://123456789012345:abcdefghijklmnopqrstuvwx@mycloud123
CLOUDINARY_FOLDER=anpr-snapshots
```

> **Format:** `cloudinary://API_KEY:API_SECRET@CLOUD_NAME`

#### 3.8. Test backend chạy được chưa

```bash
# Đảm bảo đang ở thư mục backend/ và đã activate venv
# Windows:
venv\Scripts\activate

# Chạy thử backend
python -m src.main
```

**Kết quả mong đợi:**

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     [INIT] Initializing LPR service...
INFO:     [INIT] Loading model Stage 1: stage1_detector_robust.pt ...
INFO:     [INIT] Loading model Stage 2: stage2_char_detector.pt ...
INFO:     [INIT] Loading model Stage 3: stage3_char_classify.pt ...
INFO:     [INIT] LPR service initialized successfully!
INFO:     [DB] Tables created successfully
INFO:     [SEED] Created 4 default regions
INFO:     [SEED] Created admin user: viet
INFO:     [SEED] Created 4 default cameras
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

> **Nếu thấy lỗi:** Xem [Troubleshooting](#troubleshooting--lỗi-thường-gặp)

Nhấn `Ctrl + C` để dừng backend.

---

### Bước 4: Setup Frontend (Next.js)

#### 4.1. Vào thư mục frontend

```bash
# Từ thư mục gốc dự án (không phải backend/)
cd frontend
```

#### 4.2. Cài đặt thư viện Node.js

```bash
npm install
```

Thời gian cài đặt: ~2-5 phút.

#### 4.3. Tạo file `.env.local` (tùy chọn)

Nếu bạn muốn chạy backend trên port khác hoặc trên máy khác:

```bash
# Từ thư mục frontend/
touch .env.local    # macOS/Linux
# hoặc
echo. > .env.local  # Windows
```

Nội dung file `.env.local`:

```env
# URL backend trực tiếp (dùng cho upload file lớn, vượt qua proxy 10MB của Next.js)
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000/api/v1

# URL WebSocket (Next.js rewrites KHÔNG hỗ trợ WebSocket)
NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000/api/v1/ws/lpr
```

> **Nếu không tạo file này:** Hệ thống mặc định dùng `http://127.0.0.1:8000` cho mọi request. Chỉ cần backend chạy ở localhost:8000 là OK.

#### 4.4. Test frontend chạy được chưa

```bash
npm run dev
```

**Kết quả mong đợi:**

```
  ▲ Next.js 16.2.10
  - Local:        http://localhost:3000
  - Environments: .env.local

  ✓ Starting...
  ✓ Ready in 2.5s
```

Nhấn `Ctrl + C` để dừng frontend.

---

### Bước 5: Chạy ứng dụng

#### Cách 1: Chạy cả hai cùng lúc (Khuyến nghị)

Từ **thư mục gốc** dự án (`vietnamlicenseplate/`, không phải `backend/` hay `frontend/`):

```bash
# Cài đặt concurrently (chỉ cần chạy 1 lần)
npm install

# Chạy cả backend + frontend
npm run dev
```

Kết quả:

```
[BACKEND]  INFO:     Uvicorn running on http://0.0.0.0:8000
[FRONTEND]   ▲ Next.js 16.2.10
[FRONTEND]   - Local: http://localhost:3000
```

> `concurrently` chạy song song 2 process: backend (port 8000) và frontend (port 3000).

#### Cách 2: Chạy riêng lẻ

Nếu muốn chạy riêng (ví dụ: debug backend), mở **2 terminal**:

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\activate     # Windows
# source venv/bin/activate  # macOS/Linux
python -m src.main
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

#### Truy cập ứng dụng

| Trang | URL | Mô tả |
|---|---|---|
| **Trang chủ** | http://localhost:3000 | Tự redirect → `/login` |
| **Đăng nhập** | http://localhost:3000/login | Form đăng nhập (Waze theme) |
| **Đăng ký** | http://localhost:3000/signin | Form đăng ký → OTP qua Gmail |
| **Trang nhận diện** | http://localhost:3000/home | Image, Video, Realtime tabs |
| **Live Camera** | http://localhost:3000/livecam | MJPEG grid 2×2, không cần đăng nhập |
| **Admin Dashboard** | http://localhost:3000/admin | Cần đăng nhập role `admin` |
| **Swagger API** | http://127.0.0.1:8000/docs | Tài liệu API tự động |

---

## Cấu hình môi trường chi tiết

### Backend — `backend/.env`

#### Database

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/Web_orc
```

| Phần | Giải thích |
|---|---|
| `postgresql://` | Protocol kết nối PostgreSQL |
| `postgres` | Username của PostgreSQL (mặc định là `postgres`) |
| `password` | Mật khẩu PostgreSQL bạn đặt khi cài |
| `localhost` | Server chạy trên máy local |
| `5432` | Port mặc định của PostgreSQL |
| `Web_orc` | Tên database (PHẢI viết đúng hoa thường: `Web_orc`) |

> **Nếu PostgreSQL chạy trên port khác:** Thay `5432` bằng port thực tế. Kiểm tra bằng: `psql -U postgres -c "SHOW port;"`

#### SMTP (Gmail)

```env
SMTP_USER=vietc3k49@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

| Biến | Mô tả | Giá trị |
|---|---|---|
| `SMTP_USER` | Địa chỉ Gmail gửi OTP | Gmail của bạn |
| `SMTP_PASSWORD` | App Password (16 chữ) | Tạo ở Bước 3.6 |
| `SMTP_SERVER` | Server SMTP | `smtp.gmail.com` (giữ nguyên) |
| `SMTP_PORT` | Port SMTP | `587` (giữ nguyên) |

#### Cloudinary

```env
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
CLOUDINARY_FOLDER=anpr-snapshots
```

| Biến | Mô tả |
|---|---|
| `CLOUDINARY_URL` | Chuỗi kết nối Cloudinary (format: `cloudinary://KEY:SECRET@NAME`) |
| `CLOUDINARY_FOLDER` | Tên folder lưu ảnh trên Cloudinary |

> **Để trống `CLOUDINARY_URL=""`** nếu muốn lưu local.

#### Confidence Thresholds (tùy chọn)

```env
# Nhận diện ảnh
CONF_S1_IMG=0.4    # Stage 1: Phát hiện biển số (mặc định: 0.4)
CONF_S2_IMG=0.3    # Stage 2: Phát hiện ký tự (mặc định: 0.3)
CONF_S3_IMG=0.5    # Stage 3: Phân loại ký tự (mặc định: 0.5)

# Nhận diện video
CONF_S1_VID=0.4    # Stage 1: Phát hiện biển số (mặc định: 0.4)
CONF_S2_VID=0.3    # Stage 2: Phát hiện ký tự (mặc định: 0.3)
CONF_S3_VID=0.4    # Stage 3: Phân loại ký tự (mặc định: 0.4)
```

> **Tăng threshold** → Ít kết quả nhưng chính xác hơn. **Giảm threshold** → Nhiều kết quả hơn nhưng có thể có nhiễu.

#### Device (tùy chọn)

```env
DEVICE=cuda    # Sử dụng GPU NVIDIA
# hoặc
DEVICE=cpu     # Sử dụng CPU (mặc định nếu không có GPU)
```

> Hệ thống tự động detect GPU. Chỉ cần set `DEVICE=cpu` nếu muốn ép chạy CPU.

#### Reset Database (dùng khi development)

```env
RESET_DB=1    # XÓA TOÀN BỘ dữ liệu khi khởi động (cẩn thận!)
```

> **CHỈ dùng khi development.** Sẽ `TRUNCATE` toàn bộ 9 bảng trong database.

---

### Frontend — `frontend/.env.local`

```env
# URL backend trực tiếp (cho upload file lớn >10MB)
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000/api/v1

# URL WebSocket (Next.js rewrites KHÔNG hỗ trợ WS)
NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8000/api/v1/ws/lpr
```

| Biến | Khi nào cần |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Upload video/ảnh lớn (>10MB) — vượt qua proxy 50MB của Next.js |
| `NEXT_PUBLIC_WS_URL` | WebSocket realtime — Next.js rewrites không proxy được WS |

> **Nếu không set:** Hệ thống dùng `http://127.0.0.1:8000` làm mặc định.

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
│  │  → Stage 3: Phân loại ký tự                         │ │
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
│  │  cameras                                           │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Luồng dữ liệu

```
User upload ảnh/video hoặc mở webcam
         │
         ▼
Frontend gửi request qua HTTP/WebSocket
         │
         ▼
Backend Controller nhận request
→ Delegate cho Service Layer
         │
         ▼
Service gọi AI Pipeline (3-stage YOLOv8)
→ Stage 1: Phát hiện biển số → Cắt ảnh biển số
→ Preprocessing: Deskew + Pad + Filter
→ Stage 2: Phát hiện ký tự → Cắt từng ký tự 64×64
→ Stage 3: Phân loại ký tự → Ghép chuỗi
→ Validate format biển số VN
         │
         ▼
(Không phải lần đầu) Centroid Tracking
→ Match detection với track hiện có
→ Character Voting: bỏ phiếu từng vị trí ký tự
→ Confidence = Geometric Mean từ voting
         │
         ▼
Kết quả trả về Frontend
→ Hiển thị: ảnh + bbox + plate text + confidence
→ Lưu vào PostgreSQL (detections table)
→ Upload snapshot lên Cloudinary (nếu có config)
```

---

## Công nghệ sử dụng

| Lớp | Công nghệ | Phiên bản | Mục đích |
|---|---|---|---|
| **Frontend** | Next.js (App Router) | 16.2.10 | React framework với SSR/SSG |
| | React | 19.2.4 | UI library |
| | TypeScript | 5.x | Type-safe JavaScript |
| | Tailwind CSS | 4.x | Utility-first CSS framework |
| **Backend** | Python | 3.11+ | Ngôn ngữ lập trình chính |
| | FastAPI | 0.115.12 | Web framework (async, auto-docs) |
| | SQLAlchemy | 2.0.41 | ORM (Object-Relational Mapping) |
| | Uvicorn | 0.34.2 | ASGI server |
| **Database** | PostgreSQL | 14+ | Relational database |
| **AI/ML** | Ultralytics YOLO | 8.3.163 | Object Detection & Classification |
| | OpenCV | 4.12.0.88 | Xử lý ảnh |
| | Pillow | 11.3.0 | Xử lý ảnh Python |
| | PyTorch (CUDA) | Latest | Deep learning engine |
| **Auth** | JWT (PyJWT) | 2.10.1 | JSON Web Token authentication |
| | PBKDF2-HMAC-SHA256 | — | Password hashing |
| | SMTP (Gmail) | — | Gửi OTP qua email |
| **Storage** | Cloudinary | 1.45.0 | Cloud image storage |

---

## Cấu trúc thư mục

```
vietnamlicenseplate/
│
├── package.json                    # Root: concurrently chạy backend + frontend
├── README.md                       # Tài liệu hướng dẫn (file bạn đang đọc)
├── usecase_specifications.md       # 15 formal UC specs (UC1-UC15)
│
├── docs/                           # Tài liệu thiết kế theo module
│   ├── OVERVIEW.md
│   ├── PRD.md                      # Product Requirements Document
│   ├── BR.md                       # Business Requirements
│   └── modules/
│       ├── admin/                  # spec.md, data.md, technology.md
│       ├── auth/
│       ├── detection/
│       ├── history/
│       └── region/
│
├── backend/                        # Backend Python (FastAPI)
│   ├── .env                        # ★ Cấu hình môi trường (KHÔNG commit)
│   ├── .env.example                # Mẫu file cấu hình
│   ├── requirements.txt            # Danh sách thư viện Python
│   ├── weights/                    # ★ Model YOLOv8 (KHÔNG commit)
│   │   ├── stage1_detector_robust.pt
│   │   ├── stage2_char_detector.pt
│   │   └── stage3_char_classify.pt
│   ├── static/snapshots/           # Ảnh snapshot tạm (auto-cleanup)
│   │   └── cam_{id}/               # Per-camera snapshot dirs
│   └── src/
│       ├── main.py                 # Entry point — FastAPI app, lifespan, CORS, seeding
│       ├── core/                   # Core — config & utils chung
│       │   ├── config/
│       │   │   ├── settings.py     # Cấu hình hệ thống (thresholds, DB, SMTP)
│       │   │   └── database.py     # SQLAlchemy engine, session, Base, get_db()
│       │   └── utils/
│       │       ├── security.py     # PBKDF2 password hashing
│       │       ├── email.py        # Gửi email OTP qua SMTP Gmail (HTML card template)
│       │       ├── helpers.py      # Snapshot (local + Cloudinary batch), file cleanup
│       │       └── cleanup.py      # Auto-cleanup Cloudinary + DB (7 ngày)
│       └── modules/                # Business modules (MVC pattern)
│           ├── auth/               # Xác thực
│           │   ├── routes.py       # /auth/* — register, login, OTP, logout
│           │   ├── controller.py   # Thin delegation → service
│           │   ├── service.py      # Business logic: register, OTP, login
│           │   ├── models.py       # User, Token ORM models
│           │   └── schemas.py      # Pydantic request/response schemas
│           ├── detection/          # Nhận diện biển số
│           │   ├── routes.py       # /predict-*, /tasks/*, /ws/lpr
│           │   ├── controller.py   # Thin delegation → service
│           │   ├── service.py      # Xử lý ảnh/video/WebSocket
│           │   ├── models.py       # Detection, Prediction, VideoJob, Statistics
│           │   ├── schemas.py      # Pydantic schemas
│           │   └── ai/             # AI Pipeline
│           │       ├── pipeline.py      # run_inference() — YOLOv8 3-stage
│           │       ├── preprocessing.py  # Deskew, threshold, filter, pad
│           │       ├── validation.py     # Validate format biển số VN
│           │       └── tracking.py       # CentroidTracker + Character Voting
│           ├── camera/             # Camera IP management
│           │   ├── routes.py       # /cameras/* CRUD + toggle + reset-all
│           │   ├── controller.py
│           │   ├── service.py
│           │   ├── models.py       # Camera ORM (rtsp_url, stream_url, is_active)
│           │   └── schemas.py
│           ├── admin/              # Quản trị
│           │   ├── routes.py       # /admin/* — dashboard, stats, users
│           │   ├── controller.py
│           │   ├── service.py      # Thống kê, quản lý user/region
│           │   ├── models.py       # ActivityLog ORM
│           │   └── schemas.py
│           ├── region/             # Phân vùng camera
│           │   ├── routes.py       # /regions
│           │   ├── controller.py
│           │   ├── service.py
│           │   └── models.py       # Region ORM
│           └── history/            # Lịch sử nhận diện
│               ├── routes.py       # /history
│               ├── controller.py
│               └── service.py
│
├── frontend/                       # Frontend Next.js (App Router)
│   ├── package.json
│   ├── next.config.ts              # Rewrites proxy → backend
│   ├── CLAUDE.md                   # Agent rules
│   ├── AGENTS.md                   # Next.js agent rules
│   ├── DATABASE_DESIGN.md          # Full schema, ERD
│   └── src/
│       ├── app/
│       │   ├── layout.tsx          # Root layout (font, globals.css)
│       │   ├── page.tsx            # Root → redirect /login
│       │   ├── login/page.tsx      # Trang đăng nhập (Waze theme)
│       │   ├── signin/page.tsx     # Trang đăng ký (Waze theme)
│       │   ├── home/page.tsx       # Trang chủ — Image/Video/Realtime/LiveCam tabs
│       │   ├── livecam/page.tsx    # Live Camera MJPEG — grid 2×2
│       │   └── admin/              # 8 trang quản trị
│       │       ├── layout.tsx      # Layout admin (Sidebar + TopBar)
│       │       ├── dashboard/
│       │       ├── users/
│       │       ├── verification/
│       │       ├── search/
│       │       ├── activity-log/
│       │       ├── prediction-ratio/
│       │       ├── variable-stats/
│       │       └── cameras/
│       ├── components/
│       │   ├── Navbar.tsx          # Thanh điều hướng chính
│       │   ├── LoginModal.tsx      # Modal 5 chế độ auth
│       │   ├── AnimatedBackground.tsx
│       │   ├── ImageTab.tsx        # Tab nhận diện ảnh
│       │   ├── VideoTab.tsx        # Tab nhận diện video
│       │   ├── RealtimeTab.tsx     # Tab nhận diện thời gian thực
│       │   ├── LiveCamCell.tsx     # Camera cell MJPEG
│       │   ├── LiveCamGrid.tsx     # Grid 2×2 Live Cam
│       │   ├── FullscreenView.tsx  # Fullscreen overlay
│       │   ├── SnapshotModal.tsx   # Modal xem snapshot
│       │   ├── GeneralHistoryModal.tsx
│       │   └── admin/
│       │       ├── Sidebar.tsx
│       │       ├── TopBar.tsx
│       │       └── DetectionDrilldownModal.tsx
│       ├── hooks/
│       │   └── useWebSocket.ts     # Hook WebSocket
│       ├── lib/
│       │   ├── api.ts             # API_BASE, BACKEND_URL, WS_URL
│       │   └── utils.ts           # parseVnDatetime, formatVnTime
│       └── styles/
│           └── admin.css
```

---

## Cơ sở dữ liệu (Database Schema)

Hệ thống sử dụng **9 bảng** trong PostgreSQL. Database tự động tạo khi khởi động backend lần đầu (`Base.metadata.create_all`).

### Entity Relationship Diagram (ERD)

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│    users     │       │    detections     │       │   regions    │
├──────────────┤       ├──────────────────┤       ├──────────────┤
│ id (PK)      │◄──┐   │ id (PK)          │   ┌──►│ id (PK)      │
│ username (UQ)│   │   │ plate_text       │   │   │ name         │
│ email (UQ)   │   │   │ plate_confidence │   │   │ location     │
│ full_name    │   │   │ alt_text         │   │   │ is_active    │
│ password_hash│   │   │ alt_confidence   │   │   └──────────────┘
│ role         │   │   │ total_frames     │   │
│ is_verified  │   │   │ frame_start      │   │
│ is_active    │   │   │ frame_end        │   │
│ failed_attempts│  │   │ image_path       │   │
│ created_at   │   │   │ source_type      │   │
│ last_login_at│   │   │ user_id ─────────┼───┘
│ last_logout_at│  │   │ region_id ───────┼──────► regions.id
└──────────────┘   │   │ video_job_id ────┼──────► video_jobs.id
       │           │   │ camera_id ───────┼──────► cameras.id
       │           │   │ created_at       │
       │           │   └──────────────────┘
       │           │            │
       │           │            ▼
       │           │   ┌──────────────────┐
       │           │   │   predictions     │
       │           │   ├──────────────────┤
       │           │   │ id (PK)          │
       │           │   │ detection_id (FK)│──► detections.id
       │           │   │ plate_text       │
       │           │   │ predicted_text   │
       │           │   │ is_correct       │
       │           │   │ correct_plate    │
       │           │   │ verified_by ─────┼───► users.id
       │           │   │ verified_at      │
       │           │   └──────────────────┘
       │           │
       ▼           │   ┌──────────────────┐
┌──────────────┐   │   │   video_jobs     │
│   tokens     │   │   ├──────────────────┤
├──────────────┤   │   │ id (PK)          │
│ id (PK)      │   │   │ user_id ─────────┼───► users.id
│ user_id ─────┼───┘   │ filename         │
│ token        │       │ file_path        │
│ type         │       │ file_size        │
│ expires_at   │       │ status           │
│ is_used      │       │ progress         │
│ created_at   │       │ ...              │
└──────────────┘       └──────────────────┘

┌──────────────────┐   ┌──────────────┐   ┌──────────────────┐
│  activity_logs   │   │  statistics  │   │    cameras       │
├──────────────────┤   ├──────────────┤   ├──────────────────┤
│ id (PK)          │   │ id (PK)      │   │ id (PK)          │
│ user_id ─────────┼──►│ users.id     │   │ name             │
│ action           │   │ date         │   │ rtsp_url         │
│ detail           │   │ total_detections│  │ stream_url       │
│ ip_address       │   │ avg_confidence│   │ region_id (FK)──►│──►regions.id
│ created_at       │   │ correct      │   │ is_active        │
└──────────────────┘   │ incorrect    │   │ is_online        │
                       └──────────────┘   │ fps_target       │
                                          │ description      │
                                          │ created_at       │
                                          │ updated_at       │
                                          └──────────────────┘
```

### Chi tiết từng bảng

#### 1. `users` — Tài khoản người dùng

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK, Auto-increment | Mã người dùng |
| `username` | VARCHAR(50) | UNIQUE, NOT NULL | Tên đăng nhập |
| `email` | VARCHAR(100) | UNIQUE, NOT NULL | Địa chỉ email |
| `full_name` | VARCHAR(100) | | Họ và tên |
| `password_hash` | VARCHAR(255) | NOT NULL | Mật khẩu đã mã hóa (PBKDF2) |
| `role` | VARCHAR(20) | DEFAULT 'user' | Vai trò: `user` hoặc `admin` |
| `is_verified` | INTEGER | DEFAULT 0 | Đã xác thực OTP: 0=chưa, 1=đã |
| `is_active` | BOOLEAN | DEFAULT TRUE | Tài khoản kích hoạt |
| `failed_attempts` | INTEGER | DEFAULT 0 | Số lần đăng nhập sai liên tiếp |
| `created_at` | DATETIME | DEFAULT NOW | Ngày tạo tài khoản |
| `last_login_at` | DATETIME | | Lần đăng nhập cuối |
| `last_logout_at` | DATETIME | | Lần đăng xuất cuối |

#### 2. `detections` — Kết quả nhận diện

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK, Auto-increment | Mã detection |
| `plate_text` | VARCHAR(20) | NOT NULL | Text biển số nhận diện được |
| `plate_confidence` | FLOAT | DEFAULT 0.0 | Độ tin cậy chính (0-1) |
| `alt_text` | VARCHAR(20) | | Text thay thế (alternative) |
| `alt_confidence` | FLOAT | | Độ tin cậy alternative |
| `total_frames` | INTEGER | DEFAULT 1 | Số frame nhận diện được |
| `frame_start` | INTEGER | | Frame đầu tiên detect |
| `frame_end` | INTEGER | | Frame cuối cùng detect |
| `image_path` | VARCHAR(500) | | Đường dẫn ảnh snapshot |
| `source_type` | VARCHAR(20) | DEFAULT 'camera' | Nguồn: `camera`, `image`, `video` |
| `user_id` | INTEGER | | FK → users.id (người thực hiện) |
| `region_id` | INTEGER | | FK → regions.id (khu vực) |
| `video_job_id` | INTEGER | | FK → video_jobs.id |
| `camera_id` | INTEGER | | FK → cameras.id |
| `created_at` | DATETIME | DEFAULT NOW | Thời gian nhận diện |

#### 3. `predictions` — Xác minh kết quả

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK | Mã prediction |
| `detection_id` | INTEGER | FK → detections.id | Detection được xác minh |
| `plate_text` | VARCHAR(20) | NOT NULL | Text ban đầu |
| `predicted_text` | VARCHAR(20) | NOT NULL | Text dự đoán |
| `is_correct` | INTEGER | | 1=đúng, 0=sai |
| `correct_plate` | VARCHAR(20) | | Biển số đúng (nếu sai) |
| `verified_by` | INTEGER | | FK → users.id |
| `verified_at` | DATETIME | | Thời gian xác minh |

#### 4. `video_jobs` — Tiến trình xử lý video

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK | Mã job |
| `user_id` | INTEGER | | FK → users.id |
| `filename` | VARCHAR(255) | | Tên file video |
| `file_path` | VARCHAR(500) | | Đường dẫn file tạm |
| `file_size` | INTEGER | | Kích thước file (bytes) |
| `status` | VARCHAR(20) | DEFAULT 'pending' | Trạng thái: pending/processing/completed/failed |
| `progress` | INTEGER | DEFAULT 0 | Phần trăm hoàn thành (0-100) |
| `current_frame` | INTEGER | DEFAULT 0 | Frame đang xử lý |
| `total_frames` | INTEGER | DEFAULT 0 | Tổng số frame |
| `fps` | FLOAT | | FPS của video |
| `duration` | FLOAT | | Thời lượng (giây) |
| `output_video` | VARCHAR(500) | | Đường dẫn video output |
| `output_csv` | VARCHAR(500) | | Đường dẫn file CSV |
| `output_xlsx` | VARCHAR(500) | | Đường dẫn file Excel |
| `error_message` | TEXT | | Thông báo lỗi (nếu có) |
| `created_at` | DATETIME | DEFAULT NOW | |
| `completed_at` | DATETIME | | Thời gian hoàn thành |

#### 5. `regions` — Phân vùng camera

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK | Mã phân vùng |
| `name` | VARCHAR(100) | NOT NULL | Tên phân vùng |
| `location` | VARCHAR(200) | | Mô tả vị trí |
| `is_active` | BOOLEAN | DEFAULT TRUE | Đang hoạt động |

#### 6. `cameras` — Camera IP

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK | Mã camera |
| `name` | VARCHAR(100) | NOT NULL | Tên camera |
| `rtsp_url` | VARCHAR(500) | NOT NULL | URL RTSP stream |
| `stream_url` | VARCHAR(500) | | URL MJPEG stream |
| `region_id` | INTEGER | FK → regions.id | Phân vùng |
| `is_active` | BOOLEAN | DEFAULT TRUE | Đang bật |
| `is_online` | BOOLEAN | DEFAULT FALSE | Đang kết nối |
| `fps_target` | INTEGER | DEFAULT 10 | FPS mục tiêu |
| `description` | TEXT | | Mô tả |
| `created_at` | DATETIME | DEFAULT NOW | |
| `updated_at` | DATETIME | DEFAULT NOW | Tự cập nhật |

#### 7. `tokens` — Mã OTP

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `user_id` | INTEGER | | FK → users.id |
| `token` | VARCHAR(10) | NOT NULL | Mã OTP (6 chữ số) |
| `type` | VARCHAR(20) | NOT NULL | Loại: `email_verify` hoặc `password_reset` |
| `expires_at` | DATETIME | NOT NULL | Thời gian hết hạn |
| `is_used` | BOOLEAN | DEFAULT FALSE | Đã sử dụng |
| `created_at` | DATETIME | DEFAULT NOW | |

#### 8. `statistics` — Thống kê theo ngày

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `date` | DATETIME | | Ngày thống kê |
| `total_detections` | INTEGER | DEFAULT 0 | Tổng detections |
| `avg_confidence` | FLOAT | DEFAULT 0.0 | Confidence trung bình |
| `correct` | INTEGER | DEFAULT 0 | Dự đoán đúng |
| `incorrect` | INTEGER | DEFAULT 0 | Dự đoán sai |

#### 9. `activity_logs` — Nhật ký hoạt động

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
|---|---|---|---|
| `id` | INTEGER | PK | |
| `user_id` | INTEGER | | FK → users.id |
| `action` | VARCHAR(100) | NOT NULL | Hành động (login, logout, verify, ...) |
| `detail` | VARCHAR(500) | | Chi tiết |
| `ip_address` | VARCHAR(50) | | Địa chỉ IP |
| `created_at` | DATETIME | DEFAULT NOW | |

### Seed Data (Dữ liệu mặc định)

Khi chạy backend lần đầu, hệ thống tự động tạo:

**4 Region:**
| ID | Tên | Vị trí |
|---|---|---|
| 1 | Camera Cổng Chính | Cổng chính tòa nhà A |
| 2 | Camera Cổng Phụ | Cổng phụ đường phía sau |
| 3 | Camera Hầm Gửi Xe A | Lối vào hầm A |
| 4 | Camera Hầm Gửi Xe B | Lối vào hầm B |

**4 Camera (tắt sẵn):**
| ID | Tên | Trạng thái |
|---|---|---|
| 1 | Cam Cổng Chính | Tắt, RTSP trống |
| 2 | Cam Cổng Phụ | Tắt, RTSP trống |
| 3 | Cam Hầm Gửi Xe A | Tắt, RTSP trống |
| 4 | Cam Hầm Gửi Xe B | Tắt, RTSP trống |

**1 Admin:**
| Username | Password | Email | Role |
|---|---|---|---|
| `viet` | `123456` | `vietc3k49@gmail.com` | `admin` |

---

## API Endpoints

Tất cả API nằm dưới tiền tố `/api/v1`.

### Xác thực (`/api/v1/auth`)

| Method | Endpoint | Mô tả | Request Body |
|---|---|---|---|
| POST | `/auth/register` | Đăng ký → gửi OTP qua Gmail | `{ username, email, password, full_name }` |
| POST | `/auth/verify-otp` | Xác thực OTP kích hoạt tài khoản | `{ email, otp }` |
| POST | `/auth/login` | Đăng nhập (cần tài khoản đã OTP) | `{ username, password }` |
| POST | `/auth/forgot-password` | Gửi OTP khôi phục mật khẩu | `{ email }` |
| POST | `/auth/reset-password` | Đặt lại mật khẩu bằng OTP | `{ email, otp, new_password }` |
| POST | `/auth/logout` | Đăng xuất | Header: `Authorization: Bearer <token>` |
| GET | `/auth/test-email` | Test kết nối SMTP Gmail | — |

### Nhận diện (`/api/v1`)

| Method | Endpoint | Mô tả | Parameters |
|---|---|---|---|
| POST | `/predict-image` | Upload ảnh nhận diện | `file` (multipart), `region_id` (optional) |
| POST | `/predict-video` | Upload video nhận diện | `file` (multipart), `region_id` (optional) |
| GET | `/tasks/{task_id}` | Kiểm tra tiến trình video | — |
| GET | `/tasks/{task_id}/download` | Tải video kết quả | — |
| WS | `/ws/lpr` | WebSocket realtime | Query: `region_id`, `camera_id` |

### Quản trị (`/api/v1/admin`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/admin/stats` | Thống kê tổng quan |
| GET | `/admin/users` | Danh sách người dùng |
| POST | `/admin/users` | Tạo tài khoản mới |
| PUT | `/admin/users/{user_id}/role` | Cập nhật role |
| POST | `/admin/users/{user_id}/toggle-active` | Kích hoạt / vô hiệu hóa |
| DELETE | `/admin/users/{user_id}` | Xóa người dùng |
| GET | `/admin/detections/unverified` | Danh sách chưa xác minh |
| POST | `/admin/verify-detection` | Xác minh (đúng/sai/xóa) |
| GET | `/admin/detections/incorrect` | Danh sách nhận diện sai |
| DELETE | `/admin/detections/{detection_id}` | Xóa detection |
| GET | `/admin/detections/search` | Tìm kiếm (filter: plate, source, date, region) |
| GET | `/admin/regions-stats` | Thống kê theo khu vực |
| GET | `/admin/activity-logs` | Nhật ký hoạt động |

### Phân vùng (`/api/v1`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/regions` | Danh sách phân vùng |

### Lịch sử (`/api/v1`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/history` | Lịch sử nhận diện (filter + pagination) |
| DELETE | `/history/{detection_id}` | Xóa bản ghi |

### Camera IP (`/api/v1`)

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/cameras` | Danh sách cameras |
| GET | `/cameras/{camera_id}` | Chi tiết camera |
| POST | `/cameras` | Tạo camera mới |
| PUT | `/cameras/{camera_id}` | Cập nhật camera |
| DELETE | `/cameras/{camera_id}` | Xóa camera |
| POST | `/cameras/{camera_id}/toggle` | Bật/tắt camera |
| POST | `/cameras/reset-all` | Reset tất cả cameras |

### Swagger UI

Truy cập http://127.0.0.1:8000/docs để xem tài liệu API tự động với Try-It-Out feature.

---

## AI Pipeline

### 3-Stage YOLOv8 Pipeline

```
Ảnh đầu vào (webcam / upload / video frame)
    │
    ▼
┌──────────────────────────────────────────┐
│  STAGE 1: Plate Detection                │
│  Model: stage1_detector_robust.pt        │
│  Loại: YOLOv8 Object Detection           │
│  Input: ảnh gốc (1280px)                │
│  NMS: IoU threshold = 0.5               │
│  Confidence: 0.4 (ảnh + video)          │
│  Output: bounding box các biển số        │
└──────────────┬───────────────────────────┘
               │ Cắt từng biển số theo bbox
               ▼
┌──────────────────────────────────────────┐
│  PREPROCESSING                           │
│  1. OTSU threshold                      │
│  2. minAreaRect → tìm góc xoay          │
│  3. Deskew: xoay ảnh về phương ngang    │
│     (giới hạn ±45°)                     │
│  4. Pad +8px xung quanh                 │
│  5. Grayscale + Sharpen                 │
│  6. Filter small boxes (< 70% median)   │
│  7. Sort characters by Y-gap             │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  STAGE 2: Character Detection            │
│  Model: stage2_char_detector.pt          │
│  Loại: YOLOv8 Object Detection           │
│  Input: ảnh biển số (640px)             │
│  NMS: IoU threshold = 0.3               │
│  Confidence: 0.3 (ảnh + video)          │
│  Output: bbox từng ký tự                 │
└──────────────┬───────────────────────────┘
               │ Cắt từng ký tự → Resize 64×64
               ▼
┌──────────────────────────────────────────┐
│  STAGE 3: Character Classification       │
│  Model: stage3_char_classify.pt          │
│  Loại: YOLOv8 Classification             │
│  Input: ảnh ký tự 64×64                 │
│  Confidence: 0.5 (ảnh) / 0.7 (video)   │
│  - Phân loại trên ảnh GỐC              │
│  - Lấy alternatives cho format correction│
└──────────────┬───────────────────────────┘
               │ Validate format VN
               │ Format correction (pos-based)
               │ Ghép chuỗi theo thứ tự
               ▼
         Kết quả: "51A-12345"
```

### Centroid Tracking + Character Voting (Video & Realtime)

```
Frame N:   Detect "51A-12345" bbox=[100,200,350,280]
Frame N+1: Detect "51A-12345" bbox=[102,201,352,281]  ← match
Frame N+2: Không detect được                            ← miss = 1
Frame N+3: Không detect được                            ← miss = 2
Frame N+4: Không detect được                            ← miss = 3
Frame N+5: Không detect được                            ← miss = 4 → FINALIZE
           │
           ▼
Character Voting (từng vị trí ký tự):
  Vị trí 0: '5'×5, 'S'×1  → '5' (đa số)
  Vị trí 1: '1'×6          → '1' (đồng nhất)
  Vị trí 2: 'A'×6          → 'A' (đồng nhất)
  ...
  Confidence: Geometric Mean từ character votes
  Kết quả final: "51A-12345"
```

**Matching criteria:**
- Detection match track bằng: `Combined Score = IOU×40% + TextSimilarity×40% + CentroidSimilarity×20%`
- **BẮT BUỘC** text similarity ≥ 0.5, nếu không sẽ tạo track mới

**Finalized buffer:** Chống trùng lặp — nếu detection match với track vừa finalize trong 5s → skip

**Merge buffer:** Gộp các track cùng text hoặc fuzzy match (edit_distance ≤ 1, gap ≤ 2s) → combine votes

### Snapshot Logic (Frame Đầu Tiên)

Khi track finalize (biển số biến mất khỏi khung hình), hệ thống dùng **frame đầu tiên** mà biển số xuất hiện làm ảnh snapshot:

```
Frame 1: "29A12345" conf=0.72 bbox=[100,200,350,280]
         → LƯU frame này + bbox này (first_frame_img + first_bbox)

Frame 2: "29A12345" conf=0.89 bbox=[102,201,352,281]
         → Cập nhật votes, last_bbox (KHÔNG lưu frame)

Frame 3: "29A12345" conf=0.91 bbox=[103,199,349,279]
         → Cập nhật votes, last_bbox

Frame 4-11: conf giảm dần → giữ votes

Frame 12: Biển biến消失 → FINALIZE
  → Snapshot: dùng frame 1 (ảnh + bbox đầu tiên)
  → Confidence: Geometric Mean từ character voting
  → Upload lên Cloudinary hoặc lưu local
```

---

## Các kỹ thuật xử lý

| Kỹ thuật | Mô tả | Vị trí code |
|---|---|---|
| **NMS Stage 1** | Loại bỏ box trùng lặp phát hiện biển số (IoU > 0.5) | `detection/ai/pipeline.py` |
| **NMS Stage 2** | Loại bỏ box trùng lặp ký tự (IoU > 0.3) | `detection/ai/pipeline.py` |
| **Deskew** | Xoay ảnh biển số về phương ngang (±45°) | `detection/ai/preprocessing.py` |
| **Plate Padding** | Thêm 8px padding trước khi detect ký tự | `detection/ai/preprocessing.py` |
| **Filter Small Boxes** | Lọc box quá nhỏ (< 70% median) | `detection/ai/preprocessing.py` |
| **Character Sorting** | Tách 2 dòng theo Y-gap, sort trái→phải | `detection/ai/preprocessing.py` |
| **Plate Validation** | Validate format biển số VN (8-10 ký tự) | `detection/ai/validation.py` |
| **Format Correction** | Sửa ký tự sai theo vị trí trên biển VN | `detection/ai/pipeline.py` |
| **Centroid Tracking** | Theo dõi detection qua frame (IOU + centroid + text) | `detection/ai/tracking.py` |
| **Character Voting** | Majority vote từng vị trí ký tự | `detection/ai/tracking.py` |
| **First Frame Snapshot** | Dùng frame đầu tiên làm ảnh verification | `detection/ai/tracking.py` |
| **Frame Skip** | Video xử lý ~2 FPS để tăng tốc | `detection/service.py` |
| **Miss Threshold** | 4 frame mất tín hiệu → finalize track | `detection/ai/tracking.py` |
| **Auto-cleanup** | Xóa detections + ảnh sau 7 ngày | `core/utils/cleanup.py` |

---

## Tính năng chính

### 1. Nhận diện thời gian thực (Realtime)
- Kết nối webcam qua **WebSocket** — hiển thị kết quả ngay lập tức
- **Centroid Tracking + Character Voting**: theo dõi biển số qua frame, vote ký tự tăng accuracy
- **Snapshot frame đầu tiên**: ảnh + bbox đều từ frame đầu khi biển xuất hiện
- **Batch upload Cloudinary + auto-cleanup**: ảnh tạm lưu local → batch upload khi tắt cam → auto xóa local

### 2. Live Camera — MJPEG Direct Streaming
- Grid 2×2 full-screen xem camera IP trực tiếp từ trình duyệt
- MJPG trực tiếp qua `<img src="http://ip:8080/video">` từ IP Webcam Android
- Hover → nút 🔍 phóng to full viewport
- Không cần đăng nhập

### 3. Nhận diện từ ảnh
- Upload ảnh (JPG, PNG, BMP, WebP)
- Hiển thị bounding box, text và confidence
- Lưu kết quả vào lịch sử

### 4. Nhận diện từ video
- Upload video (MP4, AVI, MOV, MKV) — xử lý nền (background thread)
- Theo dõi tiến trình real-time qua polling
- Tải video kết quả đã annotate

### 5. Quản lý người dùng & Xác thực
- Đăng ký tại `/signin`, đăng nhập tại `/login`
- Xác thực OTP qua Gmail (hoặc in console ở chế độ Dev)
- Quên mật khẩu → OTP → Đặt lại (mật khẩu mới ≠ cũ)

### 6. Dashboard quản trị (Admin)
- Thống kê tổng quan, biểu đồ theo ngày
- Xác minh kết quả: nút **Đúng** / **Sai** / **Xóa**
- Auto-replenish: sau mỗi thao tác, tự load thêm 1 biển
- Drill-down: click vào biểu đồ → modal chi tiết detection
- Quản lý users, cameras, regions

### 7. Auto-cleanup
- Xóa tự động detections + ảnh Cloudinary + file local **sau 7 ngày**
- Background task chạy mỗi **24 giờ**
- Constants: `CLEANUP_RETENTION_DAYS = 7`, `CLEANUP_INTERVAL_HOURS = 24`

---

## Tài khoản mặc định

Sau khi chạy backend lần đầu:

| Loại | Thông tin | Ghi chú |
|---|---|---|
| **Admin** | Username: `viet` / Password: `123456` | Bypass OTP, đăng nhập trực tiếp |
| **User** | Tạo qua `/auth/register` | Cần xác thực OTP trước khi đăng nhập |

---

## Hướng dẫn sử dụng

### Đăng nhập

1. Truy cập http://localhost:3000/login
2. Nhập `viet` / `123456`
3. Nhấn **Đăng nhập**

### Đăng ký tài khoản mới

1. Truy cập http://localhost:3000/signin
2. Nhập Username, Email, Password, Full Name
3. Nhấn **Đăng ký**
4. Kiểm tra email (hoặc console nếu chưa cấu hình SMTP) để lấy OTP
5. Nhập OTP → Xác thực

### Nhận diện ảnh

1. Đăng nhập → vào http://localhost:3000/home
2. Chọn tab **Image**
3. Chọn ảnh (JPG/PNG/BMP/WebP)
4. Xem kết quả: ảnh + bbox + plate text + confidence

### Nhận diện video

1. Đăng nhập → vào http://localhost:3000/home
2. Chọn tab **Video**
3. Chọn file video (MP4/AVI/MOV/MKV)
4. Đợi xử lý (hiển thị progress)
5. Tải video kết quả

### Nhận diện realtime (Webcam)

1. Đăng nhập → vào http://localhost:3000/home
2. Chọn tab **Realtime**
3. Bật webcam
4. Hướng webcam vào biển số → kết quả hiển thị real-time

### Xem Live Camera (IP Webcam)

1. Cài app **IP Webcam** trên điện thoại Android
2. Bật server trong app → ghi nhớ địa chỉ IP (ví dụ: `192.168.1.100:8080`)
3. Truy cập http://localhost:3000/livecam
4. Nhập IP + port vào ô camera
5. Nhấn **Kết nối** → xem stream MJPEG

---

## Troubleshooting — Lỗi thường gặp

### Lỗi Python không tìm thấy

```
'python' is not recognized as an internal or external command
```

**Cách fix:**
- Thử `python3` thay `python`
- Nếu Windows: kiểm tra Python đã thêm vào PATH chưa
  - Khi cài Python, tích chọn **"Add Python to PATH"**
  - Hoặc thêm thủ công: System Properties → Environment Variables → Path → thêm đường dẫn Python

### Lỗi `pip install` timeout

```
ERROR: Could not find a version that satisfies the requirement torch
```

**Cách fix:**
- Dùng mirror Việt Nam:
  ```bash
  pip install -r requirements.txt -i https://pypi.org/simple/
  ```
- Hoặc cài PyTorch riêng trước:
  ```bash
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements.txt
  ```

### Lỗi PostgreSQL connection

```
psycopg2.OperationalError: connection to server failed
```

**Cách fix:**
1. Kiểm tra PostgreSQL đã chạy chưa:
   - Windows: Services → tìm "postgresql" → Start
   - Linux: `sudo systemctl start postgresql`
2. Kiểm tra port: `psql -U postgres -c "SHOW port;"`
3. Kiểm tra password trong `.env` đúng chưa
4. Kiểm tra database `Web_orc` đã tồn tại chưa: `psql -U postgres -l`

### Lỗi thiếu file weights

```
FileNotFoundError: [Errno 2] No such file or directory: 'weights/stage1_detector_robust.pt'
```

**Cách fix:**
- Đảm bảo 3 file `.pt` nằm trong `backend/weights/`
- Không đổi tên file

### Lỗi CORS khi gọi API

```
Access to XMLHttpRequest blocked by CORS policy
```

**Cách fix:**
- Đảm bảo frontend dùng `API_BASE` (`/api/v1/...`) cho request thường (đi qua proxy Next.js)
- Chỉ dùng `BACKEND_URL` cho upload file lớn (>10MB) và WebSocket

### Backend chạy nhưng frontend không kết nối

```
Failed to fetch /api/v1/...
```

**Cách fix:**
1. Kiểm tra backend đang chạy: truy cập http://127.0.0.1:8000/docs
2. Kiểm tra `next.config.ts` có rewrites đúng chưa
3. Xóa cache Next.js: `cd frontend && rm -rf .next && npm run dev`

### Lỗi CUDA / GPU

```
RuntimeError: CUDA out of memory
```

**Cách fix:**
- Set `DEVICE=cpu` trong `.env` để chạy CPU
- Hoặc đóng các ứng dụng khác đang dùng GPU

---

## Ghi chú phát triển

- **Frontend proxy:** Next.js rewrites proxy `/api/v1/*` → `http://127.0.0.1:8000`. WebSocket và upload lớn cần kết nối trực tiếp qua `BACKEND_URL`.
- **Auto-migration:** Backend tự thêm cột mới qua `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` trong `main.py` (không dùng Alembic).
- **CORS:** Backend cho phép tất cả origins (`allow_origins=["*"]`).
- **Snapshot path:** Dùng `__file__`-based resolution trong `helpers.py` để đảm bảo path nhất quán.
- **Auto-cleanup:** Code ở `core/utils/cleanup.py`, logs `[CLEANUP]`.
- **Root `package.json`:** Dùng `concurrently` để chạy backend + frontend cùng lúc.

---

## License

Dự án © 2026 — Hệ thống Nhận diện Biển số xe Việt Nam.

Công nghệ YOLOv8 Object Detection & Classification.
