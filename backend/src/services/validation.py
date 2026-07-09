"""
Kiểm tra format biển số xe Việt Nam.
Định dạng phổ biến:
  - 2 chữ số (mã tỉnh) + 1 chữ cái (loại xe) + 4-5 chữ số
  - VD: 51A-12345, 29B1-23456, 16-F7.4438
"""
import re

# Ký tự chữ cái hợp lệ trên biển số VN (loại I, O, J, Q, W)
VALID_LETTERS = set("ABCDEFGHKLMNPRSTUVXZ")

# Ký tự chữ cái không hợp lệ ở vị trí thứ 4 (biển 5 dòng)
INVALID_LETTER_POS4 = set("IOJQW")

# Pattern cơ bản: 2 chữ số + 1 chữ cái + 4-5 chữ số
# Cho phép ngăn cách bởi -, ., space hoặc không có
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
    text = re.sub(r'\s+', '', text)  # Bỏ mọi khoảng trắng
    return text


def is_valid_plate(text: str) -> bool:
    """Kiểm tra text có đúng format biển số xe Việt Nam không.
    Trả về True nếu hợp lệ, False nếu không."""
    cleaned = clean_plate_text(text)

    # Độ dài phải là 8, 9, hoặc 10 ký tự
    if len(cleaned) < 8 or len(cleaned) > 10:
        return False

    # 2 ký tự đầu phải là số (mã tỉnh)
    if not cleaned[:2].isdigit():
        return False

    # Ký tự thứ 3 phải là chữ cái hợp lệ
    if len(cleaned) >= 3 and cleaned[2] not in VALID_LETTERS:
        return False

    # Kiểm tra pattern phổ biến
    if PLATE_PATTERN.match(cleaned):
        return True

    # Kiểm tra pattern quân đội
    if MILITARY_PATTERN.match(cleaned):
        return True

    # Pattern mở rộng: 2 số + 1 chữ + 1 chữ/số + 3-5 số (biển dài)
    if len(cleaned) >= 8:
        first2 = cleaned[:2]
        char3 = cleaned[2]
        if first2.isdigit() and char3 in VALID_LETTERS:
            # Từ vị trí 4 trở đi: chủ yếu là số
            rest = cleaned[3:]
            digit_count = sum(1 for c in rest if c.isdigit())
            if len(rest) >= 4 and digit_count / len(rest) >= 0.7:
                return True

    return False


def get_plate_format_score(text: str) -> int:
    """Đánh giá mức độ phù hợp format biển số VN theo quy luật:
      - 8-10 ký tự
      - Vị trí 0-1: số (mã tỉnh)
      - Vị trí 2: chữ cái (loại xe) ƯU TIÊN
      - Vị trí 3: chữ hoặc số (tùy model)
      - Vị trí 4+: ưu tiên số
    Trả về điểm số. 0 = không hợp lệ, càng cao càng tốt."""
    cleaned = clean_plate_text(text)

    if len(cleaned) < 8:
        return 0

    score = 0

    # Độ dài: 8 là chuẩn nhất
    if len(cleaned) == 8:
        score += 10
    elif len(cleaned) in (9, 10):
        score += 5
    else:
        return 0  # Quá ngắn hoặc quá dài

    # Vị trí 0: phải là số
    if cleaned[0].isdigit():
        score += 5
    else:
        return 0

    # Vị trí 1: phải là số
    if cleaned[1].isdigit():
        score += 5
    else:
        return 0

    # Vị trí 2: phải là chữ cái hợp lệ (ƯU TIÊN CAO)
    if cleaned[2] in VALID_LETTERS:
        score += 10
    else:
        return 0  # Bắt buộc phải là chữ

    # Vị trí 3: có thể là chữ hoặc số (tùy model quyết định)
    if len(cleaned) > 3:
        if cleaned[3].isdigit() or cleaned[3] in VALID_LETTERS:
            score += 3

    # Vị trí 4 trở đi: ưu tiên số
    for i in range(4, len(cleaned)):
        if cleaned[i].isdigit():
            score += 2
        elif cleaned[i] in VALID_LETTERS:
            score += 1  # Vẫn chấp nhận nhưng thấp hơn
        else:
            score -= 1  # Ký tự lạ

    return max(score, 0)


def get_plate_quality(text: str) -> str:
    """Đánh giá chất lượng kết quả nhận diện.
    Trả về: 'high', 'medium', 'low', 'invalid'."""
    cleaned = clean_plate_text(text)

    # Kiểm tra ký tự không xác định
    if '?' in cleaned or cleaned == '???':
        return 'invalid'

    # Kiểm tra format
    if not is_valid_plate(cleaned):
        return 'low'

    # Kiểm tra độ tin cậy dựa trên ký tự
    # Biển hợp lệ nhưng có thể cải thiện
    if len(cleaned) == 8:
        return 'high'
    elif len(cleaned) in (9, 10):
        return 'medium'

    return 'low'
