# Detection Module - Functional Specification

**Module:** Nhan dien bien so xe  
**Route prefix:** `/api/v1`  
**Files:** `routes/predict.py`, `controllers/predict_controller.py`, `services/predict_service.py`, `services/ai_pipeline.py`, `services/tracking.py`, `services/preprocessing.py`, `services/validation.py`

---

## 1. 3-Stage Pipeline Spec

### 1.1 Stage 1: Plate Detection

**Model:** `stage1_detector_robust.pt` (YOLOv8 Object Detection)  
**Input:** Anh goc (1280px cho anh, 1024px cho video, 640px cho realtime)  
**Output:** Bounding boxes cua cac bien so

**Flow:**
1. Chay YOLOv8 predict voi `imgsz` va `conf` threshold
2. Lay tat ca boxes tu `det1.boxes`
3. Ap NMS voi `iou_threshold=0.5` de loai bo box trung lap
4. Tra ve danh sach `(x1, y1, x2, y2)` cua moi bien so

### 1.2 Preprocessing (Giua Stage 1 va Stage 2)

Moi bien so duoc xu ly truoc khi chuyen den Stage 2:

```
[1] Crop: Cat bien so tu anh goc theo bounding box
[2] Deskew: Xoay ve phuong ngang
    - OTSU threshold tu dong
    - Tim contour lon nhat
    - minAreaRect -> lay goc xoay
    - Gioi han ±45°
    - Neu goc < 0.5° -> khong xoay
[3] Pad: Them 8px padding xung quanh
    - Ngan cat sat mép khi detect ky tu
[4] Preprocess: Lam sach anh
    - Grayscale (convert 'L')
    - Sharpen (ImageFilter.SHARPEN)
    - Convert lai RGB
```

### 1.3 Stage 2: Character Detection

**Model:** `stage2_char_detector.pt` (YOLOv8 Object Detection)  
**Input:** Anh bien so da xu ly (640px)  
**Output:** Bounding boxes cua cac ky tu

**Flow:**
1. Chay YOLOv8 predict voi `imgsz=640`
2. Ap NMS voi `iou_threshold=0.3`
3. Filter box nho: loai bo box co dien tích < 40% trung binh
4. Sort theo hang:
   - Tinh center Y cho moi box
   - Phan tach 2 dòng theo Y-gap lon nhat
   - Sort trai -> phai trong moi dòng

### 1.4 Stage 3: Character Classification

**Model:** `stage3_char_classify.pt` (YOLOv8 Classification)  
**Input:** Anh ky tu 64x64  
**Output:** Ky tu du doan + confidence + alternatives

**Flow:**
1. Cat ky tu tu anh bien so (sử dụng box tu Stage 2)
2. Resize 64x64
3. Chay YOLOv8 predict voi `imgsz=64`
4. Lay top-1 ky tu va confidence
5. Lay top-2 alternatives cho format correction
6. Neu confidence < threshold -> danh dau `?`

### 1.5 Format Correction (Position-Based)

Sua ky tu sai dua tren quy tac bien so VN:

```
Vi tri 0-1: BAT BUOC so (ma tinh)
    - Neu ky tu hien tai la chu -> tim alternative la so tu top-2
    - Khong tim thay -> giu nguyen

Vi tri 2: BAT BUOC chu (loai xe)
    - Neu ky tu hien tai la so -> tim alternative la chu tu top-2
    - Khong tim thay -> giu nguyen

Vi tri 3: Chu hoac so (bat ky)
    - Khong ap dung correction

Vi tri 4+: UU TIEN so
    - Neu ky tu hien tai la chu -> tim alternative la so tu top-2
    - Phat nhe 5% confidence khi thay the
```

### 1.6 Validation

Kiem tra format bien so VN:
- Do dai: 8-10 ky tu
- Vi tri 0-1: So (ma tinh)
- Vi tri 2: Chu hop le (A-Z loai I,O,J,Q,W)
- Regex pattern: `^(\d{2})([A-Z])[-.\s]?(\d{4,5})$`

---

## 2. Image Prediction Flow

```
[1] User upload anh (JPG/PNG/BMP/WebP)
    │ POST /api/v1/predict-image
    │
    ▼
[2] Validate file type
    ├── Content-type: image/*
    ├── Extension: .jpg, .jpeg, .png, .bmp, .webp
    └── Khong hop le -> 400
    │
    ▼
[3] Decode anh
    ├── Read bytes -> np.frombuffer -> cv2.imdecode
    ├── Convert BGR -> RGB
    └── Tao PIL.Image
    │
    ▼
[4] Chay AI Pipeline
    ├── init_lpr_service() -> LPRPipeline (singleton)
    ├── run_inference(pil_img, CONF_S1_IMG, CONF_S2_IMG, CONF_S3_IMG)
    └── Tra ve: [{ bbox, text, conf, char_confs }]
    │
    ▼
[5] Ve annotated image
    ├── draw_plate_results(pil_img, results)
    ├── Ve bounding box mau sac
    └── Ve nhan text + confidence
    │
    ▼
[6] Luu snapshot
    ├── save_snapshot_image(annotated_img)
    ├── Luu vao static/snapshots/{UUID}.jpg
    └── Tra ve relative path
    │
    ▼
[7] Luu vao DB
    ├── Kiem tra region_id (neu co)
    ├── Tao Detection moi voi:
    │   plate_text, plate_confidence, image_path,
    │   source_type="image", user_id, region_id
    └── DB commit
    │
    ▼
[8] Response
    { status: "success", results: [...], annotated_image: "/static/snapshots/xxx.jpg" }
```

---

## 3. Video Prediction Flow

```
[1] User upload video (MP4/AVI/MOV/MKV)
    │ POST /api/v1/predict-video
    │
    ▼
[2] Validate file type
    ├── Content-type: video/*
    ├── Extension: .mp4, .avi, .mov, .mkv
    └── Khong hop le -> 400
    │
    ▼
[3] Luu file vao temp directory
    ├── input_path = {tempdir}/{uuid}_in.{ext}
    ├── output_path = {tempdir}/{uuid}_out.mp4
    │
    ▼
[4] Tao VideoJob trong DB
    ├── status = "pending"
    ├── progress = 0
    └── Tra ve task_id
    │
    ▼
[5] Khoi chay background thread
    ├── threading.Thread(target=process_video_background)
    ├── thread.daemon = True
    └── thread.start()
    │
    ▼
[6] Response ngay lap tay
    { status: "success", task_id: "123", message: "Bat dau xu ly video." }

=== BACKGROUND THREAD ===

[7] Mo video voi OpenCV
    ├── cap = cv2.VideoCapture(input_path)
    ├── Lay metadata: total_frames, fps, width, height
    ├── Kiem tra disk space (toi thieu 500MB)
    ├── Kiem tra GPU memory (neu CUDA)
    │
    ▼
[8] Cap nhat DB: status = "processing"

[9] Tao VideoWriter
    ├── Thu mp4v codec
    ├── Neu fail -> Thu XVID codec
    ├── Neu ca hai fail -> writer = None (detection van luu)
    │
    ▼
[10] Loop qua tung frame
     ├── Frame skip: xu ly moi frame_skip frame (~2 FPS)
     │   ├── Neu skip -> Ve box cu neu trong 0.5s
     │   └── Ghi frame output
     │
     ├── Frame can inference:
     │   ├── Convert BGR -> RGB -> PIL.Image
     │   ├── run_inference(pil_img, CONF_S1_VID, ..., 1024)
     │   │   ├── Neu GPU OOM -> Fallback 640px
     │   │   └── Neu van OOM -> plates = []
     │   ├── Filter valid plates:
     │   │   ├── Khong "?"
     │   │   ├── is_valid_plate() == True
     │   │   └── get_plate_format_score() > 0
     │   ├── CentroidTracker.update(valid_plates, frame_idx, frame_img)
     │   ├── Luu finalized detections vao DB
     │   └── Ve bbox tren frame
     │
     ├── Ghi frame output voi bbox
     ├── Cap nhat progress moi 2 frame
     ├── Empty GPU cache moi 20 frame
     │
     └── Xu ly loi frame:
         ├── Skip frame
         ├── Ghi traceback vao file log
         └── Tiep tuc frame tiep theo
     │
     ▼
[11] Sau khi het video
     ├── Release cap va writer
     ├── Cleanup input file
     ├── Flush merged buffer (centroid_tracker.flush_merged())
     ├── Luu tat ca ket qua con lai vao DB
     │
     ▼
[12] Cap nhat DB: status = "completed", progress = 100

=== KET THUC BACKGROUND THREAD ===
```

---

## 4. WebSocket Realtime Flow

```
[1] Client ket noi WebSocket
    │ WS /api/v1/ws/lpr
    │
    ▼
[2] Server accept connection
    ├── Tao CentroidTracker moi
    │
    ▼
[3] Loop nhan frame tu client
     │
     ├── Nhan JSON: { image: "base64...", conf1, conf2, conf3, user_id, region_id }
     │
     ├── Validate image data
     │   ├── Khong co image -> Gui error
     │   ├── Bo dau "data:image/...;base64," neu co
     │   └── Decode base64 -> bytes -> np -> cv2 -> PIL.Image
     │
     ├── Chay AI Pipeline
     │   └── await asyncio.to_thread(
     │         service.run_inference, pil_img, conf1, conf2, conf3, 640
     │       )
     │
     ├── Filter valid plates
     │   ├── Khong "?"
     │   ├── is_valid_plate() == True
     │   └── get_plate_format_score() > 0
     │
     ├── CentroidTracker.update(valid_plates, frame_idx, frame_img)
     │   ├── Matching: IOU x 40% + Text x 40% + Centroid x 20%
     │   ├── Text similarity >= 0.5 (BAT BUOC)
     │   ├── Character Voting: gop votes qua frame
     │   ├── Miss threshold = 4 frame -> finalize
     │   ├── Merge buffer: gop track cung text
     │   └── Finalized buffer: chong trung lap 5s
     │
     ├── Luu finalized detections vao DB
     │   ├── Dung first_frame_img lam snapshot
     │   ├── Ve bounding box tren snapshot
     │   ├── save_snapshot_image()
     │   └── Tao Detection moi (source_type="camera")
     │
     ├── Gui response ve client
     │   ├── results: Bien da finalize (luu DB)
     │   └── active_plates: Bien dang track (ve bbox live)
     │
     └── Lap lai
     │
     ▼
[4] Client ngat ket noi (WebSocketDisconnect)
    └── Cleanup (khong lam gi dac biet)
```

---

## 5. Centroid Tracking + Character Voting

### 5.1 CentroidTracker

**Muc dich:** Theo doi bien so qua cac frame, tranh trung lap khi luu DB.

**Data Structure:**
```
tracks: { track_id: PlateTrack }
_finalized_buffer: [(timestamp, bbox, text, conf, hit_count)]
_merge_buffer: { text: { char_votes, char_confs, bbox, snapshot, ... } }
```

### 5.2 PlateTrack

**Muc dich:** Luu tru thong tin 1 bien so dang duoc theo doi.

**Fields:**
- `track_id`: ID duy nhat
- `centroid`: Vi tri hien tai (cx, cy)
- `plate_text`: Text moi nhat
- `last_bbox`: Bounding box moi nhat
- `miss_count`: So frame mat tin hieu
- `hit_count`: So frame phat hien duoc
- `char_votes`: `{ position: { char: vote_count } }`
- `char_confs`: `{ position: { char: sum_conf } }`
- `first_frame_img`: Frame dau tien (snapshot)
- `best_frame_img`: Frame tot nhat (conf cao nhat)
- `best_frame_conf`: Confidence cua frame tot nhat

### 5.3 Matching Algorithm

```
[1] Tinh IOU giua detection va track
[2] Tinh centroid distance similarity
    cent_sim = max(0, 1 - (dist / 100))
[3] Tinh text similarity
    text_sim = so ky tu giong / do dai chuoi dai hon
[4] BAT BUOC: text_sim >= 0.5
    Neu khong -> Khong match -> Tao track moi
[5] Combined score = IOU x 0.4 + Text x 0.4 + Centroid x 0.2
[6] Match neu: IOU >= 0.3 HOAC combined >= 0.25
[7] Chon track co combined score cao nhat
```

### 5.4 Character Voting

Khi track finalize:
```
[1] Tinh stats cho moi vi tri ky tu:
    winner = ky tu co nhieu votes nhat
    runner_up = ky tu thu hai
    margin = (winner_votes - runner_up_votes) / total_votes
    char_confidence = margin * avg_conf_of_winner

[2] Ghep text tu winner cua moi vi tri

[3] Tinh confidence = Geometric Mean cua tat ca char_confidence
    confidence = (char_conf[0] * char_conf[1] * ... * char_conf[N]) ^ (1/N)

[4] Tim alt_text tot nhat:
    Thu the runner_up tai moi vi tri
    Tinh alt_conf = Geometric Mean voi runner_up scaled by vote ratio
    Chon vi tri co alt_conf cao nhat
```

---

## 6. Snapshot Frame First Logic

### 6.1 Muc dich

Khi track finalize (biển so bien mat), he thong dung **frame dau tien** cua track lam anh snapshot verification. Dieu nay giup admin thay ro bien so o thoi diem ban dau.

### 6.2 Implementation

```
[1] Khi tao track moi:
    track.first_frame_img = frame_img  (luu frame dau tien)

[2] Khi update track:
    Neu first_frame_img is None:
        first_frame_img = frame_img  (chi luu 1 lan)
    Neu plate_conf > best_frame_conf:
        best_frame_img = frame_img  (luu frame tot nhat)
        best_frame_conf = plate_conf

[3] Khi finalize:
    snapshot_img = first_frame_img hoac best_frame_img hoac current_frame
    annotated = draw_plate_results(snapshot_img, [{bbox, text, conf}])
    save_snapshot_image(annotated) -> luu vao static/snapshots/{UUID}.jpg
```

### 6.3 Priority Order

```
1. first_frame_img (frame dau tien khi bien xuat hien)
2. best_frame_img (frame co confidence cao nhat)
3. current frame (frame hien tai)
```
