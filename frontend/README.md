# Vietnam LPR — Nhận Diện Biển Số Xe Việt Nam

Hệ thống nhận diện biển số xe Việt Nam thời gian thực sử dụng **YOLOv8 3-Stage Pipeline**.

## Công nghệ

| Layer | Stack |
|---|---|
| Backend | Python FastAPI, SQLAlchemy ORM, PostgreSQL |
| Frontend | Next.js 16 (App Router), React 19, TypeScript |
| AI Pipeline | YOLOv8 3-stage (Plate Detection → Char Detection → Char Classification) |
| Real-time | WebSocket streaming webcam từ browser |
| Auth | JWT token + OTP qua Gmail SMTP |
| Storage | Cloudinary (ưu tiên) hoặc local `static/snapshots/` |

## Chạy dự án

```bash
# Cài dependencies
npm install

# Chạy cả backend + frontend
npm run dev

# Hoặc chạy riêng
npm run dev:backend   # uvicorn, port 8000
npm run dev:frontend  # next dev, port 3000
```

## Cấu trúc dự án

```
vietnamlicenseplate/
├── backend/
│   ├── src/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── core/                   # Config & utils chung
│   │   │   ├── config/
│   │   │   │   ├── settings.py     # Pydantic Settings
│   │   │   │   └── database.py     # SQLAlchemy engine
│   │   │   └── utils/
│   │   │       ├── security.py     # PBKDF2 hash/verify
│   │   │       ├── email.py        # SMTP Gmail OTP
│   │   │       └── helpers.py      # save_snapshot, get_vietnam_now
│   │   └── modules/                # Business modules (MVC)
│   │       ├── auth/               # Xác thực
│   │       ├── detection/          # Nhận diện biển số + AI Pipeline
│   │       │   └── ai/
│   │       │       ├── pipeline.py      # 3-stage inference
│   │       │       ├── preprocessing.py # deskew, preprocess
│   │       │       ├── validation.py    # VN plate regex
│   │       │       └── tracking.py      # CentroidTracker + char voting
│   │       ├── admin/              # Quản trị
│   │       ├── region/             # Phân vùng camera
│   │       └── history/            # Lịch sử nhận diện
│   ├── weights/                    # 3 YOLOv8 .pt models
│   └── .env                        # DB + SMTP config
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router pages
│   │   ├── components/             # React components
│   │   ├── hooks/                  # Custom hooks (useWebSocket)
│   │   └── lib/                    # API constants, utils
│   └── .env.local                  # API_BASE, WS_URL
├── docs/                           # Tài liệu thiết kế
└── package.json                    # Root: concurrently runs backend + frontend
```

## AI Pipeline

```
Input Image
  → Stage 1: YOLO Plate Detection (1280px, conf=0.5)
    → NMS → Crop → Deskew → Preprocess
  → Stage 2: YOLO Char Detection (640px, conf=0.5)
    → NMS → Sort by row
  → Stage 3: YOLO Char Classification (64×64, 30 classes)
    → Position-based format correction (VN plate rules)
  → Validation (VN plate regex)
```

## Confidence Calculation (Per-Character Voting)

Confidence chỉ được tính khi biển số **biến mất** (finalize), không tính lúc real-time.

**Per-position:**
```
margin = (winner_votes - runner_up_votes) / total_votes
winner_avg_conf = sum(yolo_conf for winner) / winner_votes
char_confidence = margin × winner_avg_conf
```

**Plate confidence (Geometric Mean):**
```
plate_confidence = (char_conf[0] × char_conf[1] × ... × char_conf[n]) ^ (1/n)
```

## Camera Realtime Flow

```
Frontend                          Backend
   │                                 │
   │──── connect ws://.../ws/lpr ───→│
   │──── send frame (base64) ───────→│
   │      {image, conf1-3,           │── Stage1 → Stage2 → Stage3
   │       user_id, region_id}       │── Tracking + DB save
   │                                 │
   │←── results (finalized) ────────│  ← có confidence (tính khi finalize)
   │     {status, results,           │
   │      active_plates}             │  ← active_plates: KHÔNG có conf
   │                                 │
   │──── send next frame ───────────→│  (response-driven, ~4 FPS)
```

- **results**: Biển số đã finalize — lưu DB, hiện trong lịch sử, có confidence
- **active_plates**: Biển đang track — hiển thị live bbox trên canvas, chỉ có text (không conf)

## Database (8 Tables)

| Table | Mục đích |
|---|---|
| `regions` | Vị trí lắp camera |
| `users` | Tài khoản |
| `tokens` | OTP tokens |
| `detections` | Kết quả nhận diện |
| `predictions` | Xác minh đúng/sai |
| `statistics` | Thống kê theo ngày |
| `activity_logs` | Nhật ký |
| `video_jobs` | Job xử lý video |

## Environment

### Backend `.env`

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
```

### Frontend `.env.local`

```env
API_BASE=http://localhost:8000/api/v1
BACKEND_URL=http://localhost:8000
WS_URL=ws://localhost:8000
```
