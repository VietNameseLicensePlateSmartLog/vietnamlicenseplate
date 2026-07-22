# Phương Pháp Luận OCR — Vietnam License Plate Recognition

## Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Giai đoạn 1: Phát hiện biển số (Plate Detection)](#2-giai-đoạn-1-phát-hiện-biển-số)
3. [Giai đoạn 2: Phát hiện ký tự (Character Detection)](#3-giai-đoạn-2-phát-hiện-ký-tự)
4. [Giai đoạn 3: Phân loại ký tự (Character Classification)](#4-giai-đoạn-3-phân-loại-ký-tự)
5. [Tiền xử lý ảnh (Preprocessing)](#5-tiền-xử-lý-ảnh)
6. [Sửa chữa định dạng theo vị trí (Position-based Correction)](#6-sửa-chữa-định-dạng-theo-vị-trí)
7. [Đánh giá Confidence)](#7-tính-toán-confidence)
8. [Tracking & Character Voting (Video/Realtime)](#8-tracking--character-voting)
9. [Xác thực biển số (Validation)](#9-xác-thực-biển-số)
10. [Sơ đồ tổng thể pipeline](#10-sơ-đồ-tổng-thể-pipeline)

---

## 1. Tổng quan kiến trúc

Hệ thống sử dụng kiến trúc **3-stage YOLOv8** thay vì OCR truyền thống (CTCRNN, attention-based). Đây là phương pháp **detection-based OCR** — mỗi ký tự được phát hiện và phân loại riêng biệt bằng object detection, không dùng recognition/sequence modeling.

```
┌─────────────────────────────────────────────────────────┐
│                    3-STAGE YOLO PIPELINE                │
│                                                         │
│  Stage 1: Plate Detection      (YOLOv8 Object Detect)   │
│      ↓ crop plate                                       │
│  Stage 2: Char Detection       (YOLOv8 Object Detect)   │
│      ↓ crop each char                                   │
│  Stage 3: Char Classification  (YOLOv8 Classification)  │
│      ↓ classify 64x64 crop                              │
│  Position Correction + Confidence + Validation          │
└─────────────────────────────────────────────────────────┘
```

**Ưu điểm kiến trúc này:**
- Mỗi stage có thể fine-tune tối ưu
- Không phụ thuộc vào thứ tự ký tự (rotation-invariant)
- Hoạt động tốt với biển số 1 dòng và 2 dòng
- Batch inference ở Stage 3 → hiệu suất cao

**Nhược điểm:**
- Phụ thuộc vào chất lượng Stage 2 (phát hiện thiếu ký tự = mất ký tự)
- Không có language model / sequence correction
- Sai số tích lũy qua 3 stage

---

## 2. Giai đoạn 1: Phát hiện biển số (Plate Detection)

### Model
| Thuộc tính | Giá trị |
|---|---|
| File | `stage1_detector_robust.pt` (18.4 MB) |
| Kiểu | YOLOv8 Object Detection |
| Classes | 1 (biển số xe) |
| Input size | 1280px (image) / 1024px (video) |
| NMS IoU threshold | 0.5 |
| Confidence threshold | 0.4 (cả image & video) |

### Quy trình
```
Ảnh gốc (full frame)
  → Resize về 1280px (hoặc 1024px cho video)
  → YOLOv8 predict (conf=0.4, iou=0.5)
  → NMS lọc bỏ box trùng lặp (IoU > 0.5)
  → Output: list các bounding box [(x1,y1,x2,y2), ...]
```

### Chi tiết kỹ thuật
- NMS được thực hiện thủ công (`nms_boxes()`) với greedy approach, sắp xếp theo diện tích giảm dần
- Sau NMS, mỗi box được IoU-match lại với raw results để lấy lại confidence gốc
- Chỉ lấy box có diện tích lớn nhất khi trùng lặp (non-max suppression thực sự)

---

## 3. Giai đoạn 2: Phát hiện ký tự (Character Detection)

### Model
| Thuộc tính | Giá trị |
|---|---|
| File | `stage2_char_detector.pt` (24.5 MB) |
| Kiểu | YOLOv8 Object Detection |
| Classes | 1 (ký tự trên biển số) |
| Input size | 640px (cropped plate) |
| NMS IoU threshold | 0.3 |
| Confidence threshold | 0.3 (cả image & video) |

### Quy trình
```
Cropped plate (từ Stage 1)
  → Tiền xử lý (deskew + padding + CLAHE/sharpen)
  → YOLOv8 predict (conf=0.3, iou=0.3)
  → NMS lọc bỏ box trùng (IoU > 0.3)
  → filter_outlier_boxes(): loại box ngoài [0.7x, 1.3x] median
  → separate_characters_by_row(): phân tách thành 1-2 dòng
  → Sort each row left → right
  → Output: sorted list character bounding boxes
```


### Lọc outlier nâng cao (filter_outlier_boxes)
- Dùng **median** thay vì mean (robust hơn với outlier)
- Loại box < 70% median VÀ box > 130% median
- Nếu tất cả bị loại → trả về danh sách gốc (an toàn)

### Phân tách dòng (separate_characters_by_row)
- Tính Y-centroid của mỗi box
- Tìm gap lớn nhất giữa các centroid liền kề
- **Điều kiện tách dòng:**
  - `max_gap > median_gap × 1.5` (gap lớn hơn 50% so với gap trung bình)
  - `max_gap > avg_height × 0.4` (gap lớn hơn 40% chiều cao ký tự)
- Mỗi dòng được sort left → right riêng

---

## 4. Giai đoạn 3: Phân loại ký tự (Character Classification)

### Model
| Thuộc tính | Giá trị |
|---|---|
| File | `stage3_char_classify.pt` (12.8 MB) |
| Kiểu | YOLOv8 Classification |
| Classes | 30 (0-9, A-Z ngoại trừ I, O, J, Q, W) |
| Input size | 64×64 px |
| Confidence threshold | 0.5 (image) / 0.4 (video) |

### Tập ký tự hợp lệ (30 classes)
```
0 1 2 3 4 5 6 7 8 9
A B C D E F G H K L M N P R S T U V X Z
```
**Loại bỏ:** I, O, J, Q, W (nhầm lẫn thị giác với số hoặc không dùng trên biển VN)

### Batch inference (tối ưu hiệu suất)
```python
# THAY VÌ: predict từng ký tự → 8-9 calls/plate
# LÀM: gom tất cả ký tự từ TẤT CẢ plates → 1 batch call duy nhất
all_char_images = [...]  # flat list across all plates
results = s3_model.predict(all_char_images, imgsz=64)

# Mapping ngược về từng plate
for plate_idx, char_indices in enumerate(plate_char_indices):
    for char_idx in char_indices:
        top5 = results[char_idx].probs.top5      # ['5', '6', 'S', ...]
        top5conf = results[char_idx].probs.top5conf  # [0.82, 0.12, 0.03, ...]
```

### Xử lý đầu ra
- Lấy **top-5 predictions** cho mỗi ký tự
- Nếu top-1 confidence ≥ threshold → dùng ký tự đó
- Nếu top-1 confidence < threshold → đánh dấu `"?"` (uncertain)
- Top-5 alternatives được lưu để dùng trong position-based correction

---

## 5. Tiền xử lý ảnh (Preprocessing)

### 5.1 Deskew (chỉnh nghiêng)
```
Ảnh plate
  → Grayscale
  → OTSU threshold (BINARY_INV để contour trên ký tự trắng)
  → Tìm contour lớn nhất (nếu < 50px → giữ nguyên)
  → minAreaRect → lấy góc xoay
  → Clamp góc về [-45°, +45°]
  → Nếu |góc| < 0.5° → không xoay
  → WarpAffine xoay lại (INTER_CUBIC, border đen)
```

### 5.2 Preprocess plate cho Stage 2
```
Plate (sau deskew)
  → Thêm 8px padding đen (tránh YOLO cắt sát viền)
  → PHÂN NHÁNH:
    ├── Image mode: Grayscale → Sharpen → RGB
    └── Video mode: Grayscale → CLAHE (clipLimit=3.0, 8×8) → RGB
```

**Tại sao CLAHE cho video?** Video thường có nhiễu và ánh sáng không đều hơn ảnh tĩnh. CLAHE (Contrast Limited Adaptive Histogram Equalization) cải thiện contrast cục bộ mà không khuếch đại nhiễu.

### 5.3 Character threshold (cho Stage 3)
```
Char crop (64×64)
  → Grayscale
  → CLAHE (clipLimit=3.0, 8×8)
  → RGB
```

**Tại sao CLAHE thay vì binary threshold?** CLAHE giữ lại chi tiết anti-aliasing và nét mỏng mà binary threshold sẽ phá hủy. Điều này quan trọng cho accuracy của Stage 3.

---

## 6. Sửa chữa định dạng theo vị trí (Position-based Correction)

### Quy tắc vị trí biển số Việt Nam

| Vị trí | Loại | Giải thích |
|---|---|---|
| 0-1 | **BẮT BUỘC digit** | Mã tỉnh (VD: 29, 51, 16) |
| 2 | **BẮT BUỘC letter** | Loại xe (A, B, C, ...) từ `ABCDEFGHKLMNPRSTUVXZ` |
| 3 | Digit hoặc Letter | Seri |
| 4+ | Ưu tiên digit | Số đăng ký (thường là digit) |

### Thuật toán sửa chữa
```python
for position in plate_text:
    if top1_char is INVALID for this position:
        # Tìm trong top-5 alternatives ký tự hợp lệ nhất
        for alt_char, alt_conf in top5_alternatives:
            if alt_char IS VALID for this position:
                replace(position, alt_char)
                break
        # Nếu không có alt hợp lệ → giữ nguyên top-1
```

**Ví dụ thực tế:**
```
OCR detect: B 1 A 3 2 7 1 8
             ↑
             Vị trí 0 cần digit, nhưng 'B' là letter
             → Thử alternatives: [('B', 0.85), ('8', 0.72), ('3', 0.10)]
             → '8' là digit → thay thế

Kết quả:  8 1 A 3 2 7 1 8  ✓
```



---

## 7. Tính toán Confidence

### Confidence từng ký tự (Image mode)
- Lấy trực tiếp từ top-1 class probability của Stage 3
- Nếu < threshold → confidence = 0.0 (ký tự là "?")

### Confidence từng ký tự (Video mode — Character Voting)
Khi tracking finalize, confidence được tính dựa trên **multi-frame voting**:

```
margin = (winner_votes - runner_up_votes) / total_votes
winner_avg_conf = sum(yolo_conf của winner) / winner_votes
char_confidence[pos] = margin × winner_avg_conf
```

- **margin**: mức độ "áp đảo" của ký tự thắng so với á quân
- **winner_avg_conf**: confidence trung bình từ YOLO qua các frame
- Kết quả: ký tự thắng càng rõ ràng + YOLO conf cao → confidence cao

### Confidence cả plate (Geometric Mean)
```
plate_confidence = (char_conf[0] × char_conf[1] × ... × char_conf[n]) ^ (1/n)
```

**Tại sao geometric mean?**
- Arithmetic mean: một ký tựconf=0.1 kéo plate xuống nhẹ
- **Geometric mean**: một ký tự conf=0.1 kéo plate xuống MẠNH
-→ Bảo thủ hơn, ưu tiên plate có TẤT CẢ ký tự đều chắc chắn

### Alt text & Alt confidence
- Duyệt top-5 của từng vị trí, tìm ký tự khác top-1 có confidence cao nhất
- Alt plate confidence = geometric mean với term tại vị trí alt bị giảm theo tỷ lệ runner/winner

---

## 8. Tracking & Character Voting (Video/Realtime)

### CentroidTracker — Tổng quan
```
Frame t:   detect plates → match với tracks hiện tại → update/finalize
Frame t+1: detect plates → match → update/finalize
...
```

### Matching Criteria
Detection được match với track bằng **combined score**:
```
combined_score = IOU × 0.4 + TextSimilarity × 0.4 + CentroidSimilarity × 0.2
```

| Thành phần | Cách tính | Trọng số |
|---|---|---|
| IOU | Giao bounding box | 40% |
| Text Similarity | Ký tự khớp vị trí / max_length | 40% |
| Centroid Similarity | 1 - (khoảng cách / 100px) | 20% |

**Điều kiện match (ít nhất 1 trong 2):**
- `IOU ≥ 0.3` (trùng vị trí nhiều)
- `combined_score ≥ 0.25` (tổng điểm đủ cao)

**BẮT BUỘC:** Text similarity ≥ 0.5, nếu không → tạo track mới

### Character Voting (Bỏ phiếu ký tự)
```python
# Mỗi frame, ký tự detect được cộng vote
char_votes[position][character] += 1
char_confs[position][character] += yolo_conf

# Khi finalize: ký tự có nhiều vote nhất thắng
winner = max(char_votes[pos], key=votes.get)
```

**Ví dụ:**
```
Frame 1: "29A12345"  → votes: {0:{'2':1}, 1:{'9':1}, ...}
Frame 2: "29A12345"  → votes: {0:{'2':2}, 1:{'9':2}, ...}
Frame 3: "29A1234S"  → votes: {0:{'2':3}, 1:{'9':3}, ..., 7:{'5':2,'S':1}}
→ Position 7: '5' thắng (2 votes vs 1) → final: "29A12345"
```

### Merge Buffer (Gộp tracks)
Khi một track finalize, nó được đưa vào **merge buffer**:
- Nếu track mới có **text giống hệt** → gộp votes, giữ timestamp sớm nhất
- Nếu track mới có **edit distance ≤ 1** VÀ gap thời gian ≤ 2s → gộp
- TTL của merge buffer: 10 giây

**Mục đích:** Xe chạy qua camera có thể bị detect thành nhiều track ngắn. Merge buffer gộp chúng thành 1 detection cuối cùng với nhiều votes hơn → confidence cao hơn.

### Finalized Buffer (Chống trùng lặp)
- Sau khi finalize, track được thêm vào finalized buffer (TTL = 5s, max 20 entries)
- Detection mới match với buffer → **skip** (bỏ qua, không tạo track mới)
- Match nếu `IOU ≥ 0.3` HOẶC `text_similarity ≥ 0.8`

### Thresholds cho Video

| Threshold | Image | Video |
|---|---|---|
| Stage 1 (plate detect) | 0.4 | 0.4 |
| Stage 2 (char detect) | 0.3 | 0.3 |
| Stage 3 (char classify) | 0.5 | 0.4 |

Video dùng threshold Stage 3 thấp hơn (0.4 vs 0.5) vì frame rate cao, bù đắp bằng multi-frame voting.

---

## 9. Xác thực biển số (Validation)

### Regex patterns
```python
# Dân sự: 2 chữ số + 1 chữ cái + (tùy chọn separator) + 4-5 chữ số
PLATE_PATTERN = r'^(\d{2})([A-Z])[-.\s]?(\d{4,5})$'

# Quân sự: 2 chữ số + 1 chữ cái + 1 chữ số + (separator) + 3-5 chữ số
MILITARY_PATTERN = r'^(\d{2})([A-Z])(\d{1})[-.\s]?(\d{3,5})$'
```

### Heuristic nới lỏng (fallback)
```python
# Nếu không match regex, thử heuristic:
if len(text) >= 8
   AND text[:2].isdigit()
   AND text[2] in VALID_LETTERS
   AND percentage_of_digits(text[3:]) >= 70%
→ pass
```

### Format Quality Score
```
Length = 8:        +10 điểm (chuẩn)
Length = 9-10:     +5 điểm
Position 0 digit:  +5
Position 1 digit:  +5
Position 2 letter: +10 (quan trọng nhất)
Position 3:        +3
Position 4+: digit +2, letter +1, invalid -1
```

Plate chỉ được lưu vào DB nếu `format_score > 0`.

---

## 10. Sơ đồ tổng thể pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                        IMAGE MODE                                │
│                                                                  │
│  Upload image → Stage 1 (1280px) → crop plates                   │
│    │                                                             │
│    ├── For each plate:                                           │
│    │     Preprocess (deskew + CLAHE + padding)                   │
│    │     → Stage 2 (640px) → char bounding boxes                 │
│    │     → filter + sort rows                                    │
│    │     → Crop chars → resize 64×64                             │
│    │                                                             │
│    ├── Batch Stage 3 (all chars) → top-5 per char                │
│    │                                                             │
│    ├── Position correction (top-5 alternatives)                  │
│    ├── Confidence = geometric mean of char confs                 │
│    ├── Dedup plates (IoU > 0.4)                                  │
│    │                                                             │
│    └── Save to DB + Cloudinary snapshot                          │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     VIDEO / REALTIME MODE                        │
│                                                                  │
│  Frame t → Stage 1 → plates → preprocess → Stage 2 → chars       │
│    → Batch Stage 3 → position correction                         │
│    │                                                             │
│    ├── Filter: valid_plate() + format_score > 0 + no "?"         │
│    │                                                             │
│    ├── CentroidTracker.update(valid_plates)                      │
│    │     ├── Match: IOU×40% + TextSim×40% + CentroidSim×20%      │
│    │     ├── Update: add votes, update centroid                  │
│    │     ├── New: create PlateTrack if no match                  │
│    │     └── Miss: miss_count++ → finalize if ≥ 4 misses         │
│    │                                                             │
│    ├── Finalize: voted_text + plate_confidence (geometric mean)  │
│    │     ├── Merge buffer: gộp tracks giống nhau (edit ≤ 1)      │
│    │     └── Finalized buffer: chống trùng lặp (TTL 5s)          │
│    │                                                             │
│    └── Save finalized to DB + snapshot                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Phụ lục: Bảng so sánh với OCR truyền thống

| khía cạnh | Phương pháp này (Detection-based) | OCR truyền thống (CTCRNN/Attention) |
|---|---|---|
| Kiến trúc | 3-stage YOLO | Encoder-Decoder end-to-end |
| Xử lý 2 dòng | Separate rows by Y-centroid | Thường cần preprocessing riêng |
| Độ dài output | Tự động (từ Stage 2 detect) | Thường cố định hoặc beam search |
| Training data | bounding box labels per char | image-text pairs |
| Robustness với rotation | Tốt (YOLO rotation-invariant) | Kém hơn |
| Speed | ~4 FPS (realtime) | Thường chậm hơn |
| Language correction | Không có (chỉ position rules) | Có thể tích hợp LM |
