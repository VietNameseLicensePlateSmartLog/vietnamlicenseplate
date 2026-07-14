# Detection Module - Technology Specification

**Module:** Nhan dien bien so xe  
**Files:** `services/ai_pipeline.py`, `services/preprocessing.py`, `services/tracking.py`, `services/predict_service.py`

---

## 1. YOLOv8 Model Details

### 1.1 Three Models

| Model | File | Kieu | Input Size | Muc dich |
|---|---|---|---|---|
| **Stage 1** | `stage1_detector_robust.pt` | Object Detection | 1280/1024/640px | Phat hien bien so tren anh goc |
| **Stage 2** | `stage2_char_detector.pt` | Object Detection | 640px | Phat hien ky tu tren anh bien so |
| **Stage 3** | `stage3_char_classify.pt` | Classification | 64x64px | Phan loai tung ky tu |

### 1.2 Model Loading

```python
from ultralytics import YOLO
import os

class LPRPipeline:
    def __init__(self):
        s1_path = os.path.join(settings.WEIGHTS_DIR, 'stage1_detector_robust.pt')
        s2_path = os.path.join(settings.WEIGHTS_DIR, 'stage2_char_detector.pt')
        s3_path = os.path.join(settings.WEIGHTS_DIR, 'stage3_char_classify.pt')

        # Kiem tra file ton tai
        for path in [s1_path, s2_path, s3_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Khong tim thay file weights: {path}")

        self.stage1 = YOLO(s1_path)
        self.stage2 = YOLO(s2_path)
        self.stage3 = YOLO(s3_path)
```

### 1.3 Singleton Pattern

```python
lpr_service = None

def init_lpr_service():
    global lpr_service
    if lpr_service is None:
        lpr_service = LPRPipeline()
    return lpr_service
```

- Khoi tao 1 lan duy nhat khi app start
- Tat ca request su dung chung 1 instance
- Tranh load model nhieu lan (tốn RAM/GPU)

### 1.4 GPU Warmup

```python
if self.device == "cuda":
    # Warmup: chay 1 inference gia dinh de JIT compile CUDA kernels
    # Tranh lan dau tien cham (cold start ~5-10s)
    dummy = Image.new('RGB', (640, 640), color=(128, 128, 128))
    self.stage1.predict(dummy, imgsz=640, conf=0.5, device="cuda", verbose=False)
```

### 1.5 NMS (Non-Maximum Suppression)

**Stage 1 NMS:**
```python
raw_plate_boxes = [tuple(map(int, b.xyxy[0].tolist())) for b in det1.boxes]
plate_boxes = nms_boxes(raw_plate_boxes, iou_threshold=0.5)
```

**Stage 2 NMS:**
```python
raw_boxes = [tuple(map(int, b.xyxy[0].tolist())) for b in det2.boxes]
raw_boxes = nms_boxes(raw_boxes, iou_threshold=0.3)
```

**NMS Algorithm:**
```python
def nms_boxes(boxes, iou_threshold=0.3):
    # Sort theo dien tích giam dan
    boxes_sorted = sorted(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
    keep = []
    for box in boxes_sorted:
        is_dup = False
        for kept in keep:
            iou = compute_iou(box, kept)
            if iou > iou_threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(box)
    return keep
```

---

## 2. OpenCV Preprocessing

### 2.1 Deskew (Xoay bien so)

**Muc dich:** Xoay anh bien so ve phuong ngang de detect ky tu chinh xac hon.

**Algorithm:**
```python
def deskew_plate(plate_img):
    # 1. Convert sang grayscale
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

    # 2. OTSU threshold tu dong
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 3. Tim contour lon nhat
    contours = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max(contours, key=cv2.contourArea)

    # 4. minAreaRect -> lay goc xoay
    rect = cv2.minAreaRect(largest)
    angle = rect[-1]

    # 5. Chinh goc: minAreaRect tra goc trong [-90, 0)
    if angle < -45:
        angle = 90 + angle

    # 6. Gioi han ±45°
    angle = max(-45, min(45, angle))

    # 7. Neu goc < 0.5° -> khong xoay
    if abs(angle) < 0.5:
        return plate_img

    # 8. Xoay anh
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img_array, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(0, 0, 0))
    return Image.fromarray(rotated)
```

### 2.2 Plate Padding

**Muc dich:** Them 8px padding xung quanh anh bien so de Stage 2 detect ky tu tot hon, tranh cat sat mép.

```python
PLATE_PAD = 8

def pad_plate_crop(plate_img, pad_px=PLATE_PAD):
    arr = np.array(plate_img)
    h, w = arr.shape[:2]
    padded = np.full((h + 2*pad_px, w + 2*pad_px, arr.shape[2]), 0, dtype=np.uint8)
    padded[pad_px:pad_px+h, pad_px:pad_px+w] = arr
    return Image.fromarray(padded)
```

### 2.3 Plate Preprocessing (Stage 2)

**Muc dich:** Lam sach anh bien so truoc khi detect ky tu.

```python
def preprocess_plate(plate_img):
    gray = plate_img.convert('L')         # Grayscale
    gray = gray.filter(ImageFilter.SHARPEN)  # Sharpen
    return gray.convert('RGB')             # Convert lai RGB cho YOLO
```

### 2.4 Character Enhancement (Stage 3)

**Muc dich:** Nang contrast ky tu cho Stage 3 dual classification.

```python
def preprocess_char_threshold(char_img):
    gray = char_img.convert('L')
    arr = np.array(gray, dtype=np.uint8)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(arr)
    return Image.fromarray(enhanced).convert('RGB')
```

### 2.5 Filter Small Boxes

**Muc dich:** Loai bo box nho (nhieu) khi detect ky tu.

```python
def filter_small_boxes(boxes, min_ratio=0.4):
    if len(boxes) <= 2:
        return boxes
    areas = [(x2-x1)*(y2-y1) for x1,y1,x2,y2 in boxes]
    avg_area = sum(areas) / len(areas)
    threshold = avg_area * min_ratio
    return [box for box, area in zip(boxes, areas) if area >= threshold]
```

---

## 3. CUDA/CPU Fallback

### 3.1 Detection Logic

```python
if settings.DEVICE == "cuda" and torch.cuda.is_available():
    self.device = "cuda"
    # Log GPU info
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA: {torch.version.cuda}")
    print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
else:
    self.device = "cpu"
```

### 3.2 Model Transfer

```python
if self.device == "cuda":
    self.stage1.to("cuda")
    self.stage2.to("cuda")
    self.stage3.to("cuda")
else:
    self.stage1.to("cpu")
    self.stage2.to("cpu")
    self.stage3.to("cpu")
```

### 3.3 Runtime Fallback (GPU OOM)

```python
try:
    plates = service.run_inference(pil_img, conf1, conf2, conf3, stage1_imgsz=1024)
except torch.cuda.OutOfMemoryError:
    torch.cuda.empty_cache()
    # Fallback: giam Stage1 xuong 640px
    try:
        plates = service.run_inference(pil_img, conf1, conf2, conf3, stage1_imgsz=640)
    except Exception:
        plates = []
    torch.cuda.empty_cache()
```

### 3.4 GPU Cache Management

```python
# Moi 20 frame xu ly
if processed_count % 20 == 0 and torch.cuda.is_available():
    torch.cuda.empty_cache()
```

---

## 4. WebSocket Implementation

### 4.1 Connection

```python
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws/lpr")
async def websocket_lpr(websocket: WebSocket):
    return await PredictController.handle_websocket(websocket)
```

### 4.2 Handler

```python
@staticmethod
async def handle_websocket(websocket: WebSocket):
    await websocket.accept()
    centroid_tracker = CentroidTracker()

    try:
        while True:
            # Nhan frame tu client
            data = await websocket.receive_json()
            image_data = data.get("image")

            # Decode base64 -> PIL.Image
            if "," in image_data:
                image_data = image_data.split(",")[1]
            img_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)

            # Chay AI pipeline (async)
            service = init_lpr_service()
            results = await asyncio.to_thread(
                service.run_inference, pil_img, conf1, conf2, conf3, 640
            )

            # Tracking
            finalized = centroid_tracker.update(valid_plates, frame_idx, pil_img)

            # Luu vao DB
            for result in finalized:
                # save detection...

            # Gui ket qua
            active_plates = centroid_tracker.get_active_plates()
            await websocket.send_json({
                "status": "success",
                "results": clean_finalized,
                "active_plates": active_plates
            })

    except WebSocketDisconnect:
        pass
```

### 4.3 Async Inference

```python
# Su dung asyncio.to_thread de chay inference trong thread pool
# Khong block event loop cua FastAPI
results = await asyncio.to_thread(
    service.run_inference, pil_img, conf1, conf2, conf3, 640
)
```

---

## 5. Frame Skip Strategy

### 5.1 Video Processing

```python
# Target: xu ly ~2 FPS (moi frame ~0.5s)
target_fps = 2
frame_skip = max(1, int(fps / target_fps))

# VD: Video 30fps -> frame_skip = 15 (moi 15 frame xu ly 1 lan)
# VD: Video 60fps -> frame_skip = 30
```

### 5.2 Implementation

```python
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Skip frame: van ve box gan nhat neu trong 0.5s
    if frame_idx % frame_skip != 0:
        if last_plates and (frame_idx - last_plates_frame) <= PLATE_DISPLAY_FRAMES:
            draw_boxes_on_frame(frame, last_plates)
        # Ghi frame output (khong inference)
        writer.write(frame)
        frame_idx += 1
        continue

    # Frame can inference
    plates = service.run_inference(pil_img, ...)
    # ... tracking, save ...
    frame_idx += 1
```

### 5.3 Box Display Duration

```python
# Giu hien thi box gan nhat trong 0.5s
PLATE_DISPLAY_FRAMES = max(1, int(fps * 0.5))
# VD: 30fps -> 15 frame = 0.5s
```

---

## 6. Image Size Strategy

| Nguon | Stage 1 imgsz | Ly do |
|---|---|---|
| **Image** | 1280px | Anh tinh, chat luong cao |
| **Video** | 1024px | Can bang chat luong va toc do |
| **Realtime** | 640px | Uu toc do, WebSocket latency |
| **Video (OOM fallback)** | 64px | Fallback khi GPU OOM |

---

## 7. VideoWriter Fault Tolerance

### 7.1 Codec Fallback

```python
# Thu 1: mp4v
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

if not writer.isOpened():
    # Thu 2: XVID
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    output_path_avi = os.path.splitext(output_path)[0] + '.avi'
    writer = cv2.VideoWriter(output_path_avi, fourcc, fps, (width, height))

    if writer.isOpened():
        output_path = output_path_avi
    else:
        # Ca hai fail -> writer = None
        writer = None
        writer_enabled = False
```

### 7.2 Write Failure Recovery

```python
def _safe_write_frame(writer, frame, frame_idx, ...):
    try:
        ret = writer.write(frame)
        return writer, writer_enabled
    except Exception:
        # Thu recovery 1 lan: release -> tao lai voi XVID
        try:
            writer.release()
        except:
            pass
        try:
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            new_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            if new_writer.isOpened():
                new_writer.write(frame)
                return new_writer, True
        except:
            pass
        # Recovery that bai -> tat writer
        return None, False
```

---

## 8. Drawing Results

### 8.1 PIL Drawing (Image)

```python
def draw_plate_results(image, plates):
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    colors = ['#00FF00', '#FF8C00', '#00FFFF', '#FF00FF', '#FFFF00']

    for i, plate in enumerate(plates):
        x1, y1, x2, y2 = plate['bbox']
        color = colors[i % len(colors)]
        label = f"{plate['text']} ({plate['conf']:.2%})"

        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        draw.rectangle([x1, y1-text_h-6, x1+text_w+6, y1], fill=color)
        draw.text((x1+3, y1-text_h-4), label, fill='black', font=font)

    return annotated
```

### 8.2 OpenCV Drawing (Video)

```python
def draw_boxes_on_frame(frame, plates):
    for plate in plates:
        x1, y1, x2, y2 = plate['bbox']
        label = f"{plate['text']} {plate_conf:.2%}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
```

---

## 9. Snapshot Management

### 9.1 File Naming

```python
import uuid

def save_snapshot_image(annotated_img):
    os.makedirs("static/snapshots", exist_ok=True)
    filename = f"{uuid.uuid4()}.jpg"
    filepath = os.path.join("static", "snapshots", filename)
    annotated_img.save(filepath, format="JPEG")
    return f"/static/snapshots/{filename}"
```

### 9.2 Cleanup

```python
def cleanup_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
```

- Input video file: xoa sau khi xu ly xong
- Output video file: xoa sau khi user tai ve (background task)
