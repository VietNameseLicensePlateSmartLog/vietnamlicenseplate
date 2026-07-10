# Logic chạy 3 giai đoạn AI + Preprocessing + Validation
import os
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
from src.config.settings import settings
from src.services.preprocessing import (
    deskew_plate, preprocess_plate,
    filter_small_boxes, pad_plate_crop, PLATE_PAD
)
from src.services.validation import is_valid_plate

# ----------------- Position-based Format Correction -----------------

# Ký tự chữ cái hợp lệ trên biển số VN (loại I, O, J, Q, W)
_PLATE_VALID_LETTERS = set("ABCDEFGHKLMNPRSTUVXZ")
_PLATE_VALID_DIGITS = set("0123456789")


def _get_valid_chars_for_position(position: int, plate_length: int) -> tuple:
    """Kiểm tra loại ký tự hợp lệ cho từng vị trí trên biển số VN.
    Trả về: (digit_valid, letter_valid)
    Quy tắc:
      - Position 0-1: BẮT BUỘC số (mã tỉnh)
      - Position 2: BẮT BUỘC chữ (loại xe)
      - Position 3: Hoặc chữ hoặc số (tùy model)
      - Position 4+: Ưu tiên số, chữ bị phạt nặng"""
    if position >= plate_length:
        return (True, True)

    if position in (0, 1):
        return (True, False)       # Phải là số
    elif position == 2:
        return (False, True)       # Phải là chữ
    elif position == 3:
        return (True, True)        # Tùy model
    else:
        return (True, False)       # Ưu tiên số (chữ bị loại)


def _apply_format_correction(plate_text: str, plate_char_conf: list, alternatives_per_pos: list) -> tuple:
    """Sửa ký tự sai dựa trên quy tắc format biển số VN.
    Dùng alternatives từ Stage 3 top-2 để tìm ký tự đúng loại.
    Trả về: (corrected_text, corrected_confs)"""
    if not plate_text or len(plate_text) < 8:
        return plate_text, plate_char_conf

    corrected = list(plate_text)
    corrected_confs = list(plate_char_conf)
    length = len(plate_text)

    for i in range(length):
        digit_ok, letter_ok = _get_valid_chars_for_position(i, length)
        current_char = corrected[i]
        current_is_digit = current_char in _PLATE_VALID_DIGITS
        current_is_letter = current_char in _PLATE_VALID_LETTERS

        # Kiểm tra ký tự hiện tại có hợp lệ không
        char_valid = False
        if current_is_digit and digit_ok:
            char_valid = True
        elif current_is_letter and letter_ok:
            char_valid = True
        elif not current_is_digit and not current_is_letter:
            char_valid = True  # Ký tự đặc biệt (giữ nguyên)

        if char_valid:
            continue

        # Ký tự không hợp lệ → tìm alternatives
        alts = alternatives_per_pos[i] if i < len(alternatives_per_pos) else []

        foundReplacement = False
        for alt_char, alt_conf in alts:
            alt_is_digit = alt_char in _PLATE_VALID_DIGITS
            alt_is_letter = alt_char in _PLATE_VALID_LETTERS

            if alt_is_digit and digit_ok:
                corrected[i] = alt_char
                corrected_confs[i] = alt_conf * 0.95  # Phạt nhẹ 5%
                foundReplacement = True
                break
            elif alt_is_letter and letter_ok:
                corrected[i] = alt_char
                corrected_confs[i] = alt_conf * 0.95  # Phạt nhẹ 5%
                foundReplacement = True
                break

        # Nếu không tìm thấy alternatives phù hợp → giữ nguyên ký tự gốc

    return ''.join(corrected), corrected_confs


# ----------------- Utility Functions -----------------

def sort_chars_by_row(char_boxes):
    """Sắp xếp ký tự: hàng trên trái→phải, hàng dưới trái→phải."""
    if not char_boxes:
        return []
    items = [{'box': b, 'cy': (b[1]+b[3])/2, 'cx': (b[0]+b[2])/2} for b in char_boxes]
    items.sort(key=lambda c: c['cy'])
    if len(items) <= 1:
        return [items[0]['box']]
    gaps = [items[i+1]['cy'] - items[i]['cy'] for i in range(len(items)-1)]
    max_gap_idx = gaps.index(max(gaps))
    row_split = (items[max_gap_idx]['cy'] + items[max_gap_idx+1]['cy']) / 2
    row1 = sorted([c for c in items if c['cy'] <= row_split], key=lambda c: c['cx'])
    row2 = sorted([c for c in items if c['cy'] > row_split], key=lambda c: c['cx'])
    return [c['box'] for c in row1] + [c['box'] for c in row2]


def nms_boxes(boxes: list, iou_threshold: float = 0.3) -> list:
    if len(boxes) <= 1:
        return boxes
    boxes_sorted = sorted(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
    keep = []
    for box in boxes_sorted:
        is_dup = False
        for kept in keep:
            ix1, iy1 = max(box[0], kept[0]), max(box[1], kept[1])
            ix2, iy2 = min(box[2], kept[2]), min(box[3], kept[3])
            inter = max(0, ix2-ix1) * max(0, iy2-iy1)
            area_a = (box[2]-box[0]) * (box[3]-box[1])
            area_b = (kept[2]-kept[0]) * (kept[3]-kept[1])
            union = area_a + area_b - inter
            iou = inter / union if union > 0 else 0
            if iou > iou_threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(box)
    return keep


def draw_plate_results(image: Image.Image, plates: list) -> Image.Image:
    """Vẽ bounding box và nhãn nhận diện lên ảnh."""
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    colors = ['#00FF00', '#FF8C00', '#00FFFF', '#FF00FF', '#FFFF00']

    for i, plate in enumerate(plates):
        bbox = plate.get('bbox')
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        text = plate.get('text', '???')
        conf = plate.get('conf', 0.0)

        color = colors[i % len(colors)]

        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        label = f"{text} ({conf:.2%})"

        text_w = len(label) * 6
        text_h = 10
        if font and hasattr(draw, 'textbbox'):
            try:
                l, t, r, b = draw.textbbox((x1, y1 - text_h - 4), label, font=font)
                text_w = r - l
                text_h = b - t
            except Exception:
                pass

        draw.rectangle([x1, y1 - text_h - 6, x1 + text_w + 6, y1], fill=color)
        draw.text((x1 + 3, y1 - text_h - 4), label, fill='black', font=font)

    return annotated


# ----------------- Stage 3: Character Classification -----------------

def _predict_char(self, char_img: Image.Image, conf3: float) -> tuple:
    """Dự đoán 1 ký tự bằng Stage 3.
    Trả về: (predicted_char, confidence, alternatives)
    alternatives: list [(char, conf), ...] cho top-2 (không kể top-1)"""
    resized = char_img.resize((64, 64), Image.BILINEAR)
    pred = self.stage3.predict(resized, imgsz=64, device=self.device, verbose=False)[0]

    char, conf = '?', 0.0
    alternatives = []

    if hasattr(pred, 'probs') and pred.probs is not None:
        # Safe lookup: top1 có thể là int hoặc str tùy Ultralytics version
        top1_idx = pred.probs.top1
        names = pred.names
        if isinstance(names, dict):
            char = names.get(top1_idx, names.get(str(top1_idx), '?'))
        elif isinstance(names, (list, tuple)):
            try:
                char = names[int(top1_idx)]
            except (IndexError, ValueError):
                char = '?'
        conf = pred.probs.top1conf.item()

        # Lấy top-2 alternatives cho position-based correction
        try:
            top5 = pred.probs.top5
            top5conf = pred.probs.top5conf
            for idx in range(1, min(len(top5), 3)):  # skip top1 (index 0), lấy index 1-2
                alt_idx = top5[idx]
                if isinstance(names, dict):
                    alt_char = names.get(alt_idx, names.get(str(alt_idx), '?'))
                elif isinstance(names, (list, tuple)):
                    try:
                        alt_char = names[int(alt_idx)]
                    except (IndexError, ValueError):
                        alt_char = '?'
                alt_conf = float(top5conf[idx])
                alternatives.append((alt_char, alt_conf))
        except Exception:
            pass

    return char, conf, alternatives


# ----------------- AI Pipeline Class -----------------

class LPRPipeline:
    def __init__(self):
        s1_path = os.path.join(settings.WEIGHTS_DIR, 'stage1_detector_robust.pt')
        s2_path = os.path.join(settings.WEIGHTS_DIR, 'stage2_char_detector.pt')
        s3_path = os.path.join(settings.WEIGHTS_DIR, 'stage3_char_classify.pt')

        for path in [s1_path, s2_path, s3_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Không tìm thấy file weights YOLO tại: {os.path.abspath(path)}. "
                    "Vui lòng đảm bảo các file weights (.pt) đã được đặt đúng trong thư mục weights."
                )

        # Xác định thiết bị GPU/CPU
        if settings.DEVICE == "cuda" and torch.cuda.is_available():
            self.device = "cuda"
            print(f"[LPR] ✅ GPU detected: {torch.cuda.get_device_name(0)}")
            print(f"[LPR] CUDA version: {torch.version.cuda}")
            print(f"[LPR] GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        else:
            self.device = "cpu"
            if settings.DEVICE == "cuda":
                print("[LPR] ⚠️  CUDA not available, falling back to CPU")
            else:
                print(f"[LPR] Device set to: {self.device}")

        # Load models
        print("[LPR] Loading Stage1 (Plate Detector)...")
        self.stage1 = YOLO(s1_path)
        print("[LPR] Loading Stage2 (Char Detector)...")
        self.stage2 = YOLO(s2_path)
        print("[LPR] Loading Stage3 (Char Classifier)...")
        self.stage3 = YOLO(s3_path)

        # QUAN TRỌNG: Explicitly move models sang GPU
        # Không chỉ set device, mà phải .to(device) để models thực sự nằm trên GPU
        if self.device == "cuda":
            self.stage1.to("cuda")
            self.stage2.to("cuda")
            self.stage3.to("cuda")
            print("[LPR] ✅ All 3 models moved to GPU")
            # Warmup: chạy 1 inference giả định để JIT compile CUDA kernels
            # Tránh lần inference đầu tiên chậm (cold start ~5-10s)
            print("[LPR] Warming up GPU (first inference may take a moment)...")
            try:
                dummy = Image.new('RGB', (640, 640), color=(128, 128, 128))
                self.stage1.predict(dummy, imgsz=640, conf=0.5, device="cuda", verbose=False)
                print("[LPR] ✅ GPU warmup complete")
            except Exception as e:
                print(f"[LPR] ⚠️  Warmup failed: {e}")
        else:
            self.stage1.to("cpu")
            self.stage2.to("cpu")
            self.stage3.to("cpu")

        print(f"[LPR] Inference device: {self.device}")

    def run_inference(self, pil_img: Image.Image, conf1: float, conf2: float, conf3: float, imgsz1: int = 1280) -> list:
        """Hàm xử lý lõi nhận diện chuỗi biển số từ PIL Image.
        Luồng: Stage1 → Deskew → Pad → Preprocess → Stage2 → Filter → Sort
                → Stage3 Dual Classification → Validation → Kết quả"""
        try:
            det1 = self.stage1.predict(pil_img, imgsz=imgsz1, conf=conf1, device=self.device, verbose=False)[0]
        except KeyError as e:
            print(f"[ERROR] Stage1 predict KeyError: {e} — names={getattr(det1, 'names', 'N/A') if 'det1' in dir() else 'no det1'}")
            raise
        except Exception as e:
            print(f"[ERROR] Stage1 predict failed: {type(e).__name__}: {e}")
            raise

        # NMS trên Stage 1
        raw_plate_boxes = [tuple(map(int, b.xyxy[0].tolist())) for b in det1.boxes]
        plate_boxes = nms_boxes(raw_plate_boxes, iou_threshold=0.5)

        plates = []

        for (x1, y1, x2, y2) in plate_boxes:
            c1_conf = 0.0
            best_iou = 0.0
            for b in det1.boxes:
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
                    c1_conf = float(b.conf[0])

            # Bước 1: Crop biển số từ ảnh gốc
            plate_crop = pil_img.crop((x1, y1, x2, y2))

            # Bước 2: Deskew — chỉnh nghiêng về phương ngang
            plate_deskewed = deskew_plate(plate_crop)

            # Bước 3: Pad — thêm padding xung quanh
            plate_padded = pad_plate_crop(plate_deskewed, PLATE_PAD)

            # Bước 4: Preprocess — grayscale, contrast, sharpen
            plate_clean = preprocess_plate(plate_padded)

            # Bước 5: Stage 2 — Detect ký tự
            try:
                det2 = self.stage2.predict(plate_clean, imgsz=640, conf=conf2, device=self.device, verbose=False)[0]
            except KeyError as e:
                print(f"[ERROR] Stage2 predict KeyError: {e}")
                plates.append({'bbox': [x1, y1, x2, y2], 'text': '???', 'conf': c1_conf})
                continue
            except Exception as e:
                print(f"[ERROR] Stage2 predict failed: {type(e).__name__}: {e}")
                plates.append({'bbox': [x1, y1, x2, y2], 'text': '???', 'conf': c1_conf})
                continue
            if det2.boxes is None or len(det2.boxes) == 0:
                plates.append({'bbox': [x1, y1, x2, y2], 'text': '???', 'conf': c1_conf})
                continue

            raw_boxes = [tuple(map(int, b.xyxy[0].tolist())) for b in det2.boxes]
            raw_boxes = nms_boxes(raw_boxes, iou_threshold=0.3)

            # Bước 6: Filter box nhỏ — loại nhiễu
            raw_boxes = filter_small_boxes(raw_boxes, min_ratio=0.4)

            # Bước 7: Sort theo hàng
            char_boxes = sort_chars_by_row(raw_boxes)

            # Bước 8: Stage 3 — Dual Classification cho từng ký tự
            plate_text = ''
            plate_char_conf = []
            alternatives_per_pos = []
            for cx1, cy1, cx2, cy2 in char_boxes:
                # Crop trực tiếp từ plate_padded — boxes đã ở toa do plate_padded
                # KHÔNG trừ PLATE_PAD (pixel verification đã confirm)
                char_crop = plate_padded.crop((
                    max(0, cx1), max(0, cy1),
                    min(plate_padded.width, cx2), min(plate_padded.height, cy2)
                ))

                pred_char, pred_conf, char_alts = _predict_char(self, char_crop, conf3)

                if pred_conf >= conf3:
                    plate_text += str(pred_char)
                    plate_char_conf.append(pred_conf)
                else:
                    plate_text += '?'
                    plate_char_conf.append(0.0)
                alternatives_per_pos.append(char_alts)

            # Bước 8b: Position-based Format Correction
            # Sửa ký tự sai dựa trên quy tắc format biển số VN
            # VD: vị trí 2 là '0' (sai) → thay bằng 'U' (đúng) từ alternatives
            plate_text, plate_char_conf = _apply_format_correction(
                plate_text, plate_char_conf, alternatives_per_pos
            )

            # Bước 9: Validation — kiểm tra format biển số VN
            if plate_text and plate_text != '???' and '?' not in plate_text:
                if not is_valid_plate(plate_text):
                    # Nếu không valid, vẫn giữ kết quả nhưng đánh dấu conf thấp
                    c1_conf = min(c1_conf, 0.3)

            # Tính confidence bằng Geometric Mean (như notebook)
            # Giá trị trả về: 0.0 - 1.0 (chưa × 100)
            if plate_char_conf:
                product = 1.0
                for c in plate_char_conf:
                    product *= max(c, 1e-6)
                avg_conf = product ** (1.0 / len(plate_char_conf))
            else:
                avg_conf = c1_conf

            plates.append({
                'bbox': [x1, y1, x2, y2],
                'text': plate_text,
                'conf': avg_conf,
                'char_confs': plate_char_conf
            })

        return plates


# Khởi tạo Singleton
lpr_service = None

def init_lpr_service():
    global lpr_service
    if lpr_service is None:
        lpr_service = LPRPipeline()
    return lpr_service
