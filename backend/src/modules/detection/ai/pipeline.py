"""
3-Stage YOLOv8 Pipeline for Vietnam License Plate Recognition.
Stage 1: Phát hiện biển số (Object Detection)
Stage 2: Phát hiện ký tự (Object Detection)
Stage 3: Phân loại ký tự (Classification)

Logic khôi phục từ version cũ verified hoạt động tốt,
giữ nguyên cấu trúc thư mục MVC mới.
"""
import os
import numpy as np
import cv2
import torch
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from ultralytics import YOLO
from src.core.config.settings import settings
from src.modules.detection.ai.preprocessing import (
    preprocess_plate_image,
    preprocess_char_threshold,
    deskew_plate,
    filter_small_boxes,
    separate_characters_by_row,
)
from src.modules.detection.ai.validation import is_valid_plate

# Confidence thresholds — read from settings (env override supported)
CONF_S1_IMG = settings.CONF_S1_IMG
CONF_S2_IMG = settings.CONF_S2_IMG
CONF_S3_IMG = settings.CONF_S3_IMG

CONF_S1_VID = settings.CONF_S1_VID
CONF_S2_VID = settings.CONF_S2_VID
CONF_S3_VID = settings.CONF_S3_VID

WEIGHTS_DIR = settings.WEIGHTS_DIR

# Module-level reference to run_inference after models are loaded
_lpr_inference_fn = None

# Device for inference
_device = "cpu"

# Ký tự chữ cái hợp lệ trên biển số VN (loại I, O, J, Q, W)
_PLATE_VALID_LETTERS = set("ABCDEFGHKLMNPRSTUVXZ")
_PLATE_VALID_DIGITS = set("0123456789")

# Nguyên âm (dùng để phân biệt trong format plate)
VOWELS = set("AEIOU")


def init_lpr_service():
    """Khởi tạo mô hình YOLOv8 3-stage khi start server.
    Trả về hàm run_inference để các caller sử dụng trực tiếp."""
    global s1_model, s2_model, s3_model, _lpr_inference_fn, _device

    # Nếu đã load rồi thì trả lại function cũ (tránh load lại models)
    if _lpr_inference_fn is not None:
        return _lpr_inference_fn

    print("[LPR] 🚀 Đang tải mô hình 3-stage YOLOv8...")

    if not os.path.exists(WEIGHTS_DIR):
        raise RuntimeError(f"❌ Không tìm thấy thư mục weights: {WEIGHTS_DIR}")

    stage1_path = os.path.join(WEIGHTS_DIR, "stage1_detector_robust.pt")
    stage2_path = os.path.join(WEIGHTS_DIR, "stage2_char_detector.pt")
    stage3_path = os.path.join(WEIGHTS_DIR, "stage3_char_classify.pt")

    for path in [stage1_path, stage2_path, stage3_path]:
        if not os.path.exists(path):
            raise RuntimeError(f"❌ Không tìm thấy file weights: {path}")

    # Xác định thiết bị GPU/CPU
    if settings.DEVICE == "cuda" and torch.cuda.is_available():
        _device = "cuda"
        print(f"[LPR] ✅ GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"[LPR] CUDA version: {torch.version.cuda}")
        print(f"[LPR] GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        _device = "cpu"
        if settings.DEVICE == "cuda":
            print("[LPR] ⚠️  CUDA not available, falling back to CPU")
        else:
            print(f"[LPR] Device set to: {_device}")

    s1_model = YOLO(stage1_path)
    s2_model = YOLO(stage2_path)
    s3_model = YOLO(stage3_path)

    # Explicitly move models sang GPU
    if _device == "cuda":
        s1_model.to("cuda")
        s2_model.to("cuda")
        s3_model.to("cuda")
        print("[LPR] ✅ All 3 models moved to GPU")
        # Warmup: chạy 1 inference giả định để JIT compile CUDA kernels
        print("[LPR] Warming up GPU...")
        try:
            dummy = Image.new('RGB', (640, 640), color=(128, 128, 128))
            s1_model.predict(dummy, imgsz=640, conf=0.5, device="cuda", verbose=False)
            print("[LPR] ✅ GPU warmup complete")
        except Exception as e:
            print(f"[LPR] ⚠️  Warmup failed: {e}")
    else:
        s1_model.to("cpu")
        s2_model.to("cpu")
        s3_model.to("cpu")

    print(f"[LPR] ✅ Đã tải xong 3 mô hình YOLOv8 (device: {_device})")

    _lpr_inference_fn = run_inference
    return _lpr_inference_fn


# ===================== SORT UTILITY =====================

def sort_chars_by_row(char_boxes):
    """Sắp xếp ký tự: hàng trên trái→phải, hàng dưới trái→phải.
    Trả về list boxes đã sắp xếp."""
    if not char_boxes:
        return []
    items = [{'box': b, 'cy': (b[1] + b[3]) / 2, 'cx': (b[0] + b[2]) / 2} for b in char_boxes]
    items.sort(key=lambda c: c['cy'])
    if len(items) <= 1:
        return [items[0]['box']]
    gaps = [items[i + 1]['cy'] - items[i]['cy'] for i in range(len(items) - 1)]
    max_gap_idx = gaps.index(max(gaps))
    row_split = (items[max_gap_idx]['cy'] + items[max_gap_idx + 1]['cy']) / 2
    row1 = sorted([c for c in items if c['cy'] <= row_split], key=lambda c: c['cx'])
    row2 = sorted([c for c in items if c['cy'] > row_split], key=lambda c: c['cx'])
    return [c['box'] for c in row1] + [c['box'] for c in row2]


# ===================== NMS UTILITY =====================

def nms_boxes(boxes: list, iou_threshold: float = 0.3) -> list:
    """Non-Maximum Suppression đơn giản cho list boxes."""
    if len(boxes) <= 1:
        return boxes
    boxes_sorted = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    keep = []
    for box in boxes_sorted:
        is_dup = False
        for kept in keep:
            ix1, iy1 = max(box[0], kept[0]), max(box[1], kept[1])
            ix2, iy2 = min(box[2], kept[2]), min(box[3], kept[3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area_a = (box[2] - box[0]) * (box[3] - box[1])
            area_b = (kept[2] - kept[0]) * (kept[3] - kept[1])
            union = area_a + area_b - inter
            iou = inter / union if union > 0 else 0
            if iou > iou_threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(box)
    return keep


def _sort_bboxes_left_to_right(bboxes: list, chars: list, confs: list) -> tuple:
    """Sắp xếp bbox theo vị trí đọc tự nhiên: 2 dòng (trên/dưới), mỗi dòng trái→phải.
    Trả về: (sorted_bboxes, sorted_chars, sorted_confs)"""
    if len(bboxes) == 0:
        return bboxes, chars, confs
    if len(bboxes) <= 2:
        indices = sorted(range(len(bboxes)), key=lambda i: bboxes[i][0])
        return [bboxes[i] for i in indices], [chars[i] for i in indices], [confs[i] for i in indices]

    rows = separate_characters_by_row(bboxes)
    sorted_bboxes, sorted_chars, sorted_confs = [], [], []

    for row_indices in rows:
        row_items = [(bboxes[i], chars[i], confs[i]) for i in row_indices]
        row_items.sort(key=lambda item: item[0][0])
        for bbox, char, conf in row_items:
            sorted_bboxes.append(bbox)
            sorted_chars.append(char)
            sorted_confs.append(conf)

    return sorted_bboxes, sorted_chars, sorted_confs


def _is_valid_char_for_position(char: str, position: int, plate_length: int) -> bool:
    """Kiểm tra ký tự có hợp lệ ở vị trí trên biển số VN không.
    pos0-1: số, pos2: chữ (A-Z, loại I,O,J,Q,W), pos3: chữ hoặc số, pos4+: số
    """
    if position >= plate_length:
        return True
    if position in [0, 1]:
        return char.isdigit()
    elif position == 2:
        return char.upper() in _PLATE_VALID_LETTERS
    elif position == 3:
        return char.isdigit() or char.upper() in _PLATE_VALID_LETTERS
    else:
        return char.isdigit()


def format_plate_with_dashes(text: str) -> str:
    """Trả về text biển số VN đã clean: chỉ giữ chữ cái và số, KHÔNG thêm dấu gạch."""
    clean = text.replace(" ", "").replace(".", "").replace("-", "").upper()
    return clean


def _get_plate_length(text: str) -> int:
    """Độ dài chuẩn của biển số dựa vào ký tự đầu tiên (2 chữ số → 9, 1 chữ số → 8)."""
    clean = text.replace("-", "").replace(".", "").replace(" ", "")
    if len(clean) == 0:
        return 9
    return 9 if clean[0].isdigit() and len(clean) > 1 and clean[1].isdigit() else 8


def correct_format(plate_text: str, top1_confs: list, all_topk: list) -> str:
    """Sửa format text theo quy tắc biển số Việt Nam.
    Vị trí 0-1: số, Vị trí 2: chữ (A-Z, loại I,O,J,Q,W), Vị trí 3: chữ hoặc số, Vị trí 4+: số
    Thử thay ký tự sai bằng alternative có confidence cao nhất, giữ nguyên nếu không có."""
    plate_len = len(plate_text)

    if plate_len == 0:
        return plate_text

    result = list(plate_text)

    for i in range(plate_len):
        if i < len(all_topk) and all_topk[i]:
            current_char = result[i]
            is_valid = _is_valid_char_for_position(current_char, i, plate_len)
            if not is_valid:
                best_alt = None
                best_score = -1.0
                for alt_char, alt_conf in all_topk[i]:
                    if alt_char != current_char and _is_valid_char_for_position(alt_char, i, plate_len):
                        if alt_conf > best_score:
                            best_score = alt_conf
                            best_alt = alt_char
                if best_alt is not None:
                    result[i] = best_alt

    formatted = "".join(result)
    formatted = format_plate_with_dashes(formatted)
    return formatted


# ===================== MAIN INFERENCE =====================

def run_inference(image_source, conf1=None, conf2=None, conf3=None, mode="image", imgsz=1280, return_crop=False):
    """Chạy pipeline 3 giai đoạn trên một ảnh PIL.
    mode: 'image' dùng ngưỡng conf ảnh, 'video' dùng ngưỡng conf video.
    imgsz: kích thước input cho Stage 1 (1280 cho ảnh, 1024 cho video, 640 cho realtime).
    return_crop: nếu True, trả về thêm plate_crop_img (PIL.Image) — ảnh cắt theo bbox Stage 1.

    Trả về: list dict {
        plate_text: str, plate_confidence: float, bbox: list,
        alt_text: str | None, alt_confidence: float | None,
        char_confs: list[float],
        plate_crop_img: PIL.Image (chỉ khi return_crop=True),
    }"""
    if conf1 is None: conf1 = CONF_S1_IMG if mode == "image" else CONF_S1_VID
    if conf2 is None: conf2 = CONF_S2_IMG if mode == "image" else CONF_S2_VID
    if conf3 is None: conf3 = CONF_S3_IMG if mode == "image" else CONF_S3_VID

    is_video = (mode == "video")

    # ===== STAGE 1: Phát hiện biển số =====
    # Dùng PIL image trực tiếp cho YOLO (như code gốc verified)
    results_s1 = s1_model.predict(image_source, conf=conf1, imgsz=imgsz, iou=0.5, device=_device, verbose=False)

    if not results_s1 or len(results_s1) == 0 or results_s1[0].boxes is None or len(results_s1[0].boxes) == 0:
        return []

    # NMS trên Stage 1
    raw_plate_boxes = [tuple(map(int, b.xyxy[0].tolist())) for b in results_s1[0].boxes]
    raw_s1_confs = [float(b.conf[0]) for b in results_s1[0].boxes]
    plate_boxes = nms_boxes(raw_plate_boxes, iou_threshold=0.5)

    # DEBUG: Log Stage 1 detections
    print(f"[DEBUG-S1] Raw detections: {len(raw_plate_boxes)}, after NMS: {len(plate_boxes)}, conf1={conf1}")
    for i, (box, conf) in enumerate(zip(raw_plate_boxes, raw_s1_confs)):
        print(f"[DEBUG-S1]   Plate {i}: bbox={box}, conf={conf:.4f}")

    plates = []

    for (x1, y1, x2, y2) in plate_boxes:
        # Lấy confidence từ Stage 1 — dùng IoU matching thay vì exact match
        # (exact match có thể fail do floating point → int conversion)
        s1_conf = 0.0
        best_iou = 0.0
        for b in results_s1[0].boxes:
            bx = tuple(map(int, b.xyxy[0].tolist()))
            ix1, iy1 = max(x1, bx[0]), max(y1, bx[1])
            ix2, iy2 = min(x2, bx[2]), min(y2, bx[3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area_a = (x2 - x1) * (y2 - y1)
            area_b = (bx[2] - bx[0]) * (bx[3] - bx[1])
            union = area_a + area_b - inter
            iou = inter / union if union > 0 else 0
            if iou > best_iou:
                best_iou = iou
                s1_conf = float(b.conf[0])

        # Bước 1: Crop biển số từ ảnh PIL gốc (như code gốc)
        plate_crop = image_source.crop((x1, y1, x2, y2))

        # Bước 2-4: Deskew → Pad → Preprocess (grayscale+sharpen cho Stage 2)
        # processed_plate: grayscale → sharpen → RGB (cho Stage 2 detect ký tự)
        # plate_padded: chỉ deskew + pad, giữ RGB (cho Stage 3 crop ký tự)
        processed_plate, plate_padded = preprocess_plate_image(plate_crop, is_video=is_video)

        # ===== STAGE 2: Phát hiện ký tự =====
        # Dùng PIL Image cho YOLO predict (giống code gốc verified)
        results_s2 = s2_model.predict(processed_plate, imgsz=640, conf=conf2, device=_device, verbose=False)

        if not results_s2 or len(results_s2) == 0 or results_s2[0].boxes is None or len(results_s2[0].boxes) == 0:
            continue

        # Lấy boxes + confs từ Stage 2
        raw_char_bboxes = []
        raw_char_confs = []
        for char_box in results_s2[0].boxes:
            cx1, cy1, cx2, cy2 = map(int, char_box.xyxy[0].tolist())
            char_conf = float(char_box.conf[0])
            raw_char_bboxes.append([cx1, cy1, cx2, cy2])
            raw_char_confs.append(char_conf)

        if not raw_char_bboxes:
            continue

        # NMS trên Stage 2
        raw_tuples = [tuple(b) for b in raw_char_bboxes]
        filtered_tuples = nms_boxes(raw_tuples, iou_threshold=0.3)
        char_bboxes = [list(t) for t in filtered_tuples]

        # Lọc confs tương ứng với filtered bboxes
        char_confs = []
        for cb in char_bboxes:
            for i, orig in enumerate(raw_char_bboxes):
                if list(orig) == list(cb) and i < len(raw_char_confs):
                    char_confs.append(raw_char_confs[i])
                    break

        # Lọc box quá nhỏ (noise, nhiễu) — giữ nguyên box lớn
        # Chỉ loại box < 70% trung bình
        if char_bboxes:
            char_bboxes = filter_small_boxes(char_bboxes, min_coverage_ratio=0.7)
            # Sau khi filter, cần cập nhật lại char_confs
            new_char_confs = []
            for cb in char_bboxes:
                found = False
                for i, orig in enumerate(raw_char_bboxes):
                    if list(orig) == list(cb) and i < len(raw_char_confs):
                        new_char_confs.append(raw_char_confs[i])
                        found = True
                        break
                if not found:
                    new_char_confs.append(0.0)
            char_confs = new_char_confs

        if len(char_bboxes) == 0:
            continue

        # ===== STAGE 3: Phân loại ký tự =====
        # Sort theo hàng rồi crop từng ký tự từ processed_plate (PIL)
        sorted_bboxes = sort_chars_by_row(char_bboxes)

        all_chars_text = []
        all_chars_confs = []
        all_topk_per_char = []
        actual_char_bboxes = []

        for bbox in sorted_bboxes:
            cx1, cy1, cx2, cy2 = bbox
            # Crop từ plate_padded (RGB gốc, đã deskew+pad) — KHÔNG dùng processed_plate
            # Vì processed_plate đã grayscale → mất info màu cho Stage 3 classification
            # boxes đang ở tọa độ plate_padded nên KHÔNG trừ padding
            char_img = plate_padded.crop((
                max(0, cx1), max(0, cy1),
                min(plate_padded.width, cx2), min(plate_padded.height, cy2)
            ))
            char_img_resized = char_img.resize((64, 64), Image.BILINEAR)

            # Dùng PIL Image cho YOLO predict (giống code gốc)
            results_s3 = s3_model.predict(char_img_resized, imgsz=64, device=_device, verbose=False)

            if results_s3 and len(results_s3) > 0 and results_s3[0].probs is not None:
                top5_indices = results_s3[0].probs.top5
                top5_confs = results_s3[0].probs.top5conf.tolist()
                class_names = results_s3[0].names

                if top5_indices and len(top5_indices) > 0:
                    top1_idx = top5_indices[0]
                    top1_conf = top5_confs[0]
                    top1_char = class_names[top1_idx]

                    # Dùng conf3 (threshold từ settings) thay vì CHAR_MIN_CONF hardcoded
                    # conf3 = 0.3 cho ảnh, 0.7 cho video (như code gốc)
                    if top1_conf >= conf3:
                        all_chars_text.append(top1_char)
                        all_chars_confs.append(top1_conf)
                    else:
                        all_chars_text.append("?")
                        all_chars_confs.append(0.0)

                    # Lấy alternatives cho format correction (top-2 trở đi)
                    topk = []
                    for idx, conf in zip(top5_indices, top5_confs):
                        topk.append((class_names[idx], conf))
                    all_topk_per_char.append(topk)
                else:
                    all_chars_text.append("?")
                    all_chars_confs.append(0.0)
                    all_topk_per_char.append([])
            else:
                all_chars_text.append("?")
                all_chars_confs.append(0.0)
                all_topk_per_char.append([])

            actual_char_bboxes.append(bbox)

        if not all_chars_text:
            continue

        # Sort lại cho khớp
        sorted_bboxes_final = actual_char_bboxes
        sorted_chars = all_chars_text
        sorted_confs = all_chars_confs
        sorted_topk = all_topk_per_char

        plate_text = "".join(sorted_chars)

        plate_text = correct_format(plate_text, sorted_confs, sorted_topk)

        plate_length = _get_plate_length(plate_text)
        if len(plate_text) != plate_length and len(plate_text) > plate_length:
            plate_text = plate_text[:plate_length]

        # Confidence = Geometric Mean (như notebook gốc — chính xác hơn arithmetic mean)
        if sorted_confs:
            product = 1.0
            for c in sorted_confs:
                product *= max(c, 1e-6)
            plate_confidence = product ** (1.0 / len(sorted_confs))
        else:
            plate_confidence = s1_conf

        # Tính alt_text — ký tự thay thế có confidence cao nhất
        alt_text = None
        alt_confidence = None
        for i in range(len(sorted_topk)):
            if i < len(sorted_topk) and sorted_topk[i]:
                for alt_char, alt_conf in sorted_topk[i]:
                    if i < len(sorted_chars) and alt_char != sorted_chars[i]:
                        alt_text = alt_char
                        alt_confidence = alt_conf
                        break
            if alt_text:
                break

        plate_entry = {
            "plate_text": plate_text,
            "plate_confidence": round(plate_confidence, 6),
            "alt_text": alt_text,
            "alt_confidence": round(alt_confidence, 6) if alt_confidence is not None else None,
            "bbox": [x1, y1, x2, y2],
            "char_confs": sorted_confs,
        }
        if return_crop:
            plate_entry["plate_crop_img"] = plate_crop
        plates.append(plate_entry)

    # ===== POST-PROCESSING: Giữ nguyên ALL plates (như code gốc verified) =====
    # Code gốc KHÔNG filter ở đây — việc validate để caller xử lý
    # (filter quá mạnh ở đây sẽ loại bỏ plates hợp lệ khi Stage 3 miss 1-2 ký tự)
    print(f"[DEBUG-PP] Final plates: {len(plates)} plates")
    for i, p in enumerate(plates):
        clean_text = p["plate_text"].replace("-", "").replace("?", "")
        print(f"[DEBUG-PP]   Plate {i}: text='{p['plate_text']}', clean='{clean_text}', len={len(clean_text)}, conf={p['plate_confidence']:.4f}")

    # Deduplicate — giữ detection tốt nhất cho cùng 1 vị trí
    if len(plates) > 1:
        plates = _deduplicate_plates(plates)

    return plates


def _deduplicate_plates(plates: list) -> list:
    """Loại bỏ detection trùng lặp: chỉ dedup khi bbox overlap cao.
    KHÔNG dedup theo text nếu bbox ở vị trí khác nhau (2 xe khác nhau có thể cùng biển)."""
    if len(plates) <= 1:
        return plates

    # Sắp xếp theo confidence giảm dần
    plates_sorted = sorted(plates, key=lambda p: p["plate_confidence"], reverse=True)
    keep = []

    for plate in plates_sorted:
        is_dup = False
        bx1, by1, bx2, by2 = plate["bbox"]
        area_a = (bx2 - bx1) * (by2 - by1)

        for kept in keep:
            kx1, ky1, kx2, ky2 = kept["bbox"]
            ix1, iy1 = max(bx1, kx1), max(by1, ky1)
            ix2, iy2 = min(bx2, kx2), min(by2, ky2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area_b = (kx2 - kx1) * (ky2 - ky1)
            union = area_a + area_b - inter
            iou = inter / union if union > 0 else 0

            # IoU > 0.4 → trùng vị trí
            if iou > 0.4:
                is_dup = True
                break

            # Overlap > 60% diện tích nhỏ hơn → gần như chứa nhau
            if min(area_a, area_b) > 0:
                overlap_ratio = inter / min(area_a, area_b)
                if overlap_ratio > 0.6:
                    is_dup = True
                    break

        if not is_dup:
            keep.append(plate)

    return keep


def draw_plate_results(image_source, results: list) -> Image.Image:
    """Vẽ bounding box + label lên ảnh PIL. Trả về ảnh PIL RGB mới.
    Font size tỷ lệ với chiều cao bbox, label không bị tràn ảnh."""
    img = image_source.copy().convert("RGB")
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size

    colors = ['#00FF00', '#FF8C00', '#00FFFF', '#FF00FF', '#FFFF00']

    for i, plate in enumerate(results):
        x1, y1, x2, y2 = plate["bbox"]
        text = plate.get("plate_text") or plate.get("text", "")
        conf = plate.get("plate_confidence") or plate.get("conf", 0.0)

        color = colors[i % len(colors)]

        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        label = f"{text} ({conf:.2%})"

        # Tính font size tỷ lệ với chiều cao bbox (max 16px, min 10px)
        bbox_h = y2 - y1
        font_size = max(10, min(16, int(bbox_h * 0.4)))
        font = ImageFont.load_default(size=font_size)

        # Đo kích thước text động
        try:
            l, t, r, b = draw.textbbox((0, 0), label, font=font)
            text_w = r - l
            text_h = b - t
        except Exception:
            text_w = int(len(label) * (font_size * 0.6))
            text_h = font_size

        # Vẽ label background + text phía trên bbox
        label_y = y1 - text_h - 6
        label_x = x1

        # Giới hạn không vượt ảnh
        if label_y < 0:
            label_y = y1 + 2  # Nếu không đủ chỗ phía trên, vẽ trong bbox
        if label_x + text_w + 6 > img_w:
            label_x = max(0, img_w - text_w - 6)  # Cạnh phải không tràn

        draw.rectangle([label_x, label_y, label_x + text_w + 6, label_y + text_h + 4], fill=color)
        draw.text((label_x + 3, label_y + 2), label, fill='black', font=font)

    return img
