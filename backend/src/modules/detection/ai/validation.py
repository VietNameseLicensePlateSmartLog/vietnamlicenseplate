"""
Validation: Kiểm tra format biển số xe Việt Nam.
Định dạng phổ biến:
  - 2 chữ số (mã tỉnh) + 1 chữ cái (loại xe) + 4-5 chữ số
  - VD: 51A-12345, 29B1-23456, 16-F7.4438
"""
import re

# Ký tự chữ cái hợp lệ trên biển số VN (loại I, O, J, Q, W)
VALID_LETTERS = set("ABCDEFGHKLMNPRSTUVXZ")

# Pattern cơ bản: 2 chữ số + 1 chữ cái + 4-5 chữ số
PLATE_PATTERN = re.compile(
    r'^(\d{2})'           # 2 chữ số đầu (mã tỉnh)
    r'([A-Z])'            # 1 chữ cái (loại xe)
    r'[-.\s]?'            # separator tùy chọn
    r'(\d{4,5})$'         # 4-5 chữ số
)

# Pattern cho biển quân đội: 2 chữ số + chữ cái đặc biệt + ...
MILITARY_PATTERN = re.compile(
    r'^(\d{2})'
    r'([A-Z])'
    r'(\d{1})'
    r'[-.\s]?'
    r'(\d{3,5})$'
)


def clean_plate_text(text: str) -> str:
    """Làm sạch text biển số: loại bỏ space thừa, chuyển uppercase."""
    text = text.strip().upper()
    text = re.sub(r'\s+', '', text)
    return text


def is_valid_plate(text: str) -> bool:
    """Kiểm tra text có đúng format biển số xe Việt Nam không."""
    cleaned = clean_plate_text(text)

    if len(cleaned) < 8 or len(cleaned) > 10:
        return False

    if not cleaned[:2].isdigit():
        return False

    if len(cleaned) >= 3 and cleaned[2] not in VALID_LETTERS:
        return False

    if PLATE_PATTERN.match(cleaned):
        return True

    if MILITARY_PATTERN.match(cleaned):
        return True

    # Pattern mở rộng: 2 số + 1 chữ + rest chủ yếu là số
    if len(cleaned) >= 8:
        first2 = cleaned[:2]
        char3 = cleaned[2]
        if first2.isdigit() and char3 in VALID_LETTERS:
            rest = cleaned[3:]
            digit_count = sum(1 for c in rest if c.isdigit())
            if len(rest) >= 4 and digit_count / len(rest) >= 0.7:
                return True

    return False


def get_plate_format_score(text: str) -> float:
    """Tính điểm format biển số VN. 0.0 = sai, càng cao càng tốt.
    Vị trí 0-1: số, vị trí 2: chữ (A-Z, loại I,O,J,Q,W), vị trí 3: chữ hoặc số, vị trí 4+: ưu tiên số."""
    cleaned = clean_plate_text(text)

    if len(cleaned) < 8 or len(cleaned) > 10:
        return 0.0

    score = 0.0

    # Độ dài: 8 là chuẩn nhất
    if len(cleaned) == 8:
        score += 10.0
    elif len(cleaned) in (9, 10):
        score += 5.0
    else:
        return 0.0

    # Vị trí 0: phải là số
    if cleaned[0].isdigit():
        score += 5.0
    else:
        return 0.0

    # Vị trí 1: phải là số
    if cleaned[1].isdigit():
        score += 5.0
    else:
        return 0.0

    # Vị trí 2: phải là chữ cái hợp lệ (ƯU TIẾN CAO)
    if cleaned[2] in VALID_LETTERS:
        score += 10.0
    else:
        return 0.0

    # Vị trí 3: có thể là chữ hoặc số
    if len(cleaned) > 3:
        if cleaned[3].isdigit() or cleaned[3] in VALID_LETTERS:
            score += 3.0

    # Vị trí 4 trở đi: ưu tiên số
    for i in range(4, len(cleaned)):
        if cleaned[i].isdigit():
            score += 2.0
        elif cleaned[i] in VALID_LETTERS:
            score += 1.0
        else:
            score -= 1.0

    return max(score, 0.0)
