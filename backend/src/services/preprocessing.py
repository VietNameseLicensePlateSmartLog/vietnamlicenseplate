"""
Các kỹ thuật tiền xử lý ảnh cho Pipeline 3 Stage LPR.
Bao gồm: Deskew, Preprocess Plate, Preprocess Char Threshold,
Filter Small Boxes, Plate Padding.
"""
import cv2
import numpy as np
from PIL import Image, ImageOps, ImageFilter


# ======================== DESKEW ========================

def deskew_plate(plate_img: Image.Image) -> Image.Image:
    """Xoay ảnh biển số về phương ngang (deskew) dựa trên contour lớn nhất.
    Giới hạn góc xoay ±45° để tránh xoay sai."""
    img_array = np.array(plate_img)
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # OTSU threshold tự động
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return plate_img

    # Lấy contour lớn nhất
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 50:
        return plate_img

    rect = cv2.minAreaRect(largest)
    angle = rect[-1]

    # minAreaRect trả góc trong [-90, 0)
    if angle < -45:
        angle = 90 + angle

    # Giới hạn ±45°
    angle = max(-45, min(45, angle))

    if abs(angle) < 0.5:
        return plate_img  # Góc quá nhỏ, không cần xoay

    h, w = img_array.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img_array, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0)
    )
    return Image.fromarray(rotated)


# ================ PREPROCESS PLATE (Stage 2) ================

def preprocess_plate(plate_img: Image.Image) -> Image.Image:
    """Làm sạch và tối ưu ảnh biển số trước khi detect ký tự (Stage 2).
    Grayscale → Sharpen → RGB."""
    gray = plate_img.convert('L')

    gray = gray.filter(ImageFilter.SHARPEN)
    return gray.convert('RGB')


# ============= PREPROCESS CHAR ENHANCE (Stage 3) =============

def preprocess_char_threshold(char_img: Image.Image) -> Image.Image:
    """Nâng contrast ảnh ký tự cho Stage 3 dual classification.
    CLAHE (Contrast Limited Adaptive Histogram Equalization).
    Giữ chi tiết anti-aliasing, không mất stroke mảnh như binary threshold."""
    gray = char_img.convert('L')
    arr = np.array(gray, dtype=np.uint8)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(arr)
    return Image.fromarray(enhanced).convert('RGB')


def preprocess_char_binary(char_img: Image.Image, ratio: float = 0.65) -> Image.Image:
    """Binary threshold cũ (giữ lại để debug/so sánh)."""
    gray = char_img.convert('L')
    arr = np.array(gray, dtype=np.float32)
    mean_val = arr.mean()
    threshold = mean_val * ratio
    arr = np.where(arr > threshold, 255, 0).astype(np.uint8)
    return Image.fromarray(arr).convert('RGB')


# ============= FILTER SMALL BOXES ================

def filter_small_boxes(boxes: list, min_ratio: float = 0.4) -> list:
    """Loại bỏ bounding box có diện tích nhỏ hơn min_ratio × trung bình.
    Dùng để lọc nhiễu khi detect ký tự."""
    if len(boxes) <= 2:
        return boxes

    areas = [(x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in boxes]
    avg_area = sum(areas) / len(areas)
    threshold = avg_area * min_ratio

    return [box for box, area in zip(boxes, areas) if area >= threshold]


# ================ PLATE PADDING ================

PLATE_PAD = 8  # Số pixel padding xung quanh biển số

def pad_plate_crop(plate_img: Image.Image, pad_px: int = PLATE_PAD) -> Image.Image:
    """Thêm padding xung quanh ảnh biển số crop để Stage 2 detect ký tự tốt hơn,
    tránh cắt sát mép."""
    arr = np.array(plate_img)
    h, w = arr.shape[:2]

    # Tạo ảnh mới với padding
    if len(arr.shape) == 3:
        padded = np.full((h + 2 * pad_px, w + 2 * pad_px, arr.shape[2]), 0, dtype=np.uint8)
    else:
        padded = np.full((h + 2 * pad_px, w + 2 * pad_px), 0, dtype=np.uint8)

    padded[pad_px:pad_px + h, pad_px:pad_px + w] = arr
    return Image.fromarray(padded)
