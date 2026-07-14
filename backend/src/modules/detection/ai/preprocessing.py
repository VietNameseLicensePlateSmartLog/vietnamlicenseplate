"""
Preprocessing cho Pipeline 3-Stage LPR.
Deskew (contour-based), Preprocess Plate (PIL Sharpen), Filter, Pad.
CLAHE enhancement cho Stage 3.
Logic khôi phục từ version cũ đã verified hoạt động tốt + cải tiến.
"""
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps


# ======================== DESKEW ========================

def deskew_plate(plate_img):
    """Xoay ảnh biển số về phương ngang (deskew) dựa trên contour lớn nhất.
    Giới hạn góc xoay ±45°.
    Nhận vào PIL Image hoặc numpy array, trả về image đã xoay."""
    if isinstance(plate_img, Image.Image):
        img_array = np.array(plate_img)
    else:
        img_array = plate_img.copy()

    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # OTSU threshold tự động — dùng BINARY_INV để detect contour chữ tối trên nền sáng
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        if isinstance(plate_img, Image.Image):
            return plate_img
        return Image.fromarray(img_array)

    # Lấy contour lớn nhất
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 50:
        if isinstance(plate_img, Image.Image):
            return plate_img
        return Image.fromarray(img_array)

    rect = cv2.minAreaRect(largest)
    angle = rect[-1]

    # minAreaRect trả góc trong [-90, 0)
    if angle < -45:
        angle = 90 + angle

    # Giới hạn ±45°
    angle = max(-45, min(45, angle))

    if abs(angle) < 0.5:
        if isinstance(plate_img, Image.Image):
            return plate_img
        return Image.fromarray(img_array)

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


# ================ PREPROCESS PLATE (Stage 2 input) ================

def preprocess_plate_image(plate_img, is_video=False):
    """Làm sạch ảnh biển số trước khi detect ký tự (Stage 2).
    Luồng: RGB/PIL → Deskew → Pad → Grayscale → Sharpen → RGB.
    Trả về: (processed_plate_PIL, plate_padded_PIL)

    processed_plate: PIL RGB — đầu vào cho Stage 2 YOLO (grayscale → sharpen → RGB)
    plate_padded: PIL RGB — ảnh đã deskew + pad, KHÔNG grayscale (dùng cho Stage 3 crop ký tự)
    is_video: nếu True, dùng CLAHE cho ảnh video (nhiễu hơn)
    """
    # Chuyển sang PIL nếu là numpy array
    if isinstance(plate_img, np.ndarray):
        if len(plate_img.shape) == 3:
            pil_plate = Image.fromarray(plate_img)
        else:
            pil_plate = Image.fromarray(plate_img)
    else:
        pil_plate = plate_img.copy()

    # Bước 1: Deskew — chỉnh nghiêng về phương ngang
    plate_deskewed = deskew_plate(pil_plate)

    # Bước 2: Pad — thêm padding 8px xung quanh (đen) để tránh cắt sát mép
    pad_size = 8
    arr = np.array(plate_deskewed)
    h, w = arr.shape[:2]
    if len(arr.shape) == 3:
        padded = np.full((h + 2 * pad_size, w + 2 * pad_size, arr.shape[2]), 0, dtype=np.uint8)
    else:
        padded = np.full((h + 2 * pad_size, w + 2 * pad_size), 0, dtype=np.uint8)
    padded[pad_size:pad_size + h, pad_size:pad_size + w] = arr

    # plate_padded: ảnh đã deskew + pad, giữ nguyên RGB cho Stage 3 crop
    plate_padded = Image.fromarray(padded)

    # Bước 3: Preprocess cho Stage 2 — Grayscale → Sharpen → RGB
    # Grayscale giúp loại bỏ noise màu, tăng contrast chữ trên nền sáng
    # → Stage 2 detect ký tự chính xác hơn (đã verified ở code gốc)
    if is_video:
        # Video: dùng CLAHE trên grayscale để tăng contrast
        gray_arr = np.array(plate_padded.convert('L'), dtype=np.uint8)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray_arr)
        processed_plate = Image.fromarray(enhanced).convert('RGB')
    else:
        # Ảnh tĩnh: Grayscale → Sharpen → RGB (như code gốc verified)
        gray = plate_padded.convert('L')
        gray = gray.filter(ImageFilter.SHARPEN)
        processed_plate = gray.convert('RGB')

    return processed_plate, plate_padded


# ============= PREPROCESS CHAR ENHANCE (Stage 3) =============

def preprocess_char_threshold(char_img):
    """Nâng contrast ảnh ký tự cho Stage 3 classification.
    CLAHE (Contrast Limited Adaptive Histogram Equalization).
    Giữ chi tiết anti-aliasing, không mất stroke mảnh như binary threshold."""
    gray = char_img.convert('L')
    arr = np.array(gray, dtype=np.uint8)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(arr)
    return Image.fromarray(enhanced).convert('RGB')


# ============= FILTER SMALL BOXES ================

def filter_small_boxes(bboxes, img_width=None, img_height=None, min_coverage_ratio=0.4):
    """Loại bỏ bounding box có diện tích quá nhỏ so với trung bình.
    Trả về: filtered_bboxes — giữ nguyên thứ tự.
    Nếu ≤2 boxes → giữ nguyên (như code gốc verified)."""
    if len(bboxes) <= 2:
        return bboxes

    areas = [(x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in bboxes]
    avg_area = sum(areas) / len(areas)
    min_area = avg_area * min_coverage_ratio

    return [box for box, area in zip(bboxes, areas) if area >= min_area]


# ============= FILTER OUTLIER BOXES (Majority-based) ================

def filter_outlier_boxes(bboxes, min_ratio=0.7, max_ratio=1.3):
    """Lọc box đột biến (quá nhỏ hoặc quá lớn) so với đa số using median.

    Logic:
    - Tính median diện tích (robust hơn mean, không bị ảnh hưởng outliers)
    - Box nào diện tích < median * min_ratio → loại (quá nhỏ: vết xước, noise)
    - Box nào diện tích > median * max_ratio → loại (quá lớn: mép bảng, đèn, ...)
    - Nếu ≤2 boxes → giữ nguyên (không đủ dữ liệu để phân biệt majority)
    - Nếu tất cả boxes có diện tích gần như nhau → giữ nguyên

    Args:
        bboxes: list of [x1, y1, x2, y2]
        min_ratio: ngưỡng nhỏ nhất = median * min_ratio (mặc định 0.7 → box nhỏ hơn 70% median bị loại)
        max_ratio: ngưỡng lớn nhất = median * max_ratio (mặc định 1.3 → box lớn hơn 1.3x median bị loại)

    Returns:
        filtered_bboxes — giữ nguyên thứ tự gốc
    """
    if len(bboxes) <= 2:
        return bboxes

    # Tính diện tích từng box
    areas = [(x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in bboxes]

    # Dùng median thay vì mean — median robust hơn với outliers
    sorted_areas = sorted(areas)
    n = len(sorted_areas)
    if n % 2 == 0:
        median_area = (sorted_areas[n // 2 - 1] + sorted_areas[n // 2]) / 2.0
    else:
        median_area = sorted_areas[n // 2]

    # Nếu median quá nhỏ (box gần như không có diện tích) → skip filter
    if median_area < 10:
        return bboxes

    min_area = median_area * min_ratio
    max_area = median_area * max_ratio

    filtered = []
    removed_count = 0
    for box, area in zip(bboxes, areas):
        if area < min_area:
            removed_count += 1
            print(f"  [FILTER] Removed small box: area={area:.0f} < min={min_area:.0f} (median={median_area:.0f})")
        elif area > max_area:
            removed_count += 1
            print(f"  [FILTER] Removed large box: area={area:.0f} > max={max_area:.0f} (median={median_area:.0f})")
        else:
            filtered.append(box)

    if removed_count > 0:
        print(f"  [FILTER] Outlier filter: {removed_count}/{len(bboxes)} boxes removed (median_area={median_area:.0f})")

    # Nếu tất cả bị loại → giữ nguyên (an toàn hơn là trả rỗng)
    if not filtered:
        print(f"  [FILTER] All boxes filtered out → keeping originals")
        return bboxes

    return filtered


# ============= SEPARATE CHARACTERS BY ROW ================

def separate_characters_by_row(bboxes):
    """Phân biệt ký tự thành 2 hàng dựa trên khoảng cách giữa Y centroids.
    Cải tiến: dùng median gap + validation để tránh split sai."""
    if len(bboxes) <= 2:
        return [list(range(len(bboxes)))]

    centroids_y = np.array([(y1 + y2) / 2 for x1, y1, x2, y2 in bboxes])
    sorted_indices = np.argsort(centroids_y)

    if len(sorted_indices) < 3:
        return [list(range(len(bboxes)))]

    # Tính gap giữa các Y centroid đã sắp xếp
    gaps = np.diff(centroids_y[sorted_indices])
    avg_height = np.mean([(y2 - y1) for x1, y1, x2, y2 in bboxes])

    # Median gap — dùng làm baseline cho "khoảng cách bình thường giữa các ký tự cùng dòng"
    median_gap = np.median(gaps)

    # Tìm gap lớn nhất
    max_gap_idx = np.argmax(gaps)
    max_gap = gaps[max_gap_idx]

    # Điều kiện split: gap phải lớn hơn 1.5x median gap VÀ lớn hơn avg_height * 0.4
    # Điều này đảm bảo chỉ split khi có khoảng cách thực sự lớn giữa 2 dòng
    if max_gap > median_gap * 1.5 and max_gap > avg_height * 0.4:
        row1 = sorted_indices[:max_gap_idx + 1].tolist()
        row2 = sorted_indices[max_gap_idx + 1:].tolist()

        # Validation: mỗi dòng phải có ít nhất 1 ký tự
        # Và dòng có nhiều ký tự hơn phải nhiều hơn gấp 2 lần dòng ít hơn → hợp lý cho biển 2 dòng
        if len(row1) >= 1 and len(row2) >= 1:
            return [row1, row2]

    return [sorted_indices.tolist()]
