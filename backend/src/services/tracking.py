"""
Video Tracking: IOU + Centroid Matching + Character-level Voting.
Theo dõi biển số qua các frame, gộp kết quả bằng voting để tăng độ chính xác.
Sử dụng IOU bbox làm tiêu chí match chính, centroid distance làm phụ.
Bao gồm finalized buffer: chống trùng lặp khi track finalizes rồi detect lại.
"""
import time
import numpy as np
from collections import defaultdict
from src.services.validation import get_plate_format_score


MISS_THRESHOLD = 8        # Sau 8 frame mất tín hiệu → finalize (~4s ở 2 FPS)
MIN_HITS = 2              # Tối thiểu 2 hit trước khi finalize (chống fake)
CENTROID_DISTANCE = 100   # Ngưỡng khoảng cách Euclid (backup khi IOU thấp)
IOU_THRESHOLD = 0.3       # Ngưỡng IOU tối thiểu để match
MIN_MATCH_SCORE = 0.25    # Ngưỡng combined score tối thiểu để match
FINALIZED_BUFFER_TTL = 5.0  # Thời gian nhớ track đã finalize (giây)
FINALIZED_BUFFER_MAX = 20   # Số track tối đa trong buffer
VOTE_MARGIN = 1.2         # Margin giữa top1/top2 phiếu để tính confidence

# Merge config (từ video-process.ipynb)
MERGE_BUFFER_TTL = 10.0   # Thời gian giữ kết quả đã merge (giây)
MERGE_EDIT_DISTANCE = 1   # Edit distance tối đa để fuzzy merge
MERGE_TIME_GAP = 2.0      # Khoảng thời gian tối đa giữa 2 track để fuzzy merge (giây)


def _compute_iou(box_a, box_b) -> float:
    """Tính Intersection over Union (IOU) giữa hai bounding box."""
    if not box_a or not box_b:
        return 0.0
    ix1 = max(box_a[0], box_b[0])
    iy1 = max(box_a[1], box_b[1])
    ix2 = min(box_a[2], box_b[2])
    iy2 = min(box_a[3], box_b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _compute_text_similarity(text_a: str, text_b: str) -> float:
    """Tính text similarity giữa 2 biển số (0.0 → 1.0)."""
    if not text_a or not text_b:
        return 0.0
    a = text_a.replace("-", "").replace(".", "").replace(" ", "").upper()
    b = text_b.replace("-", "").replace(".", "").replace(" ", "").upper()
    if a == b:
        return 1.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 0.0
    matches = sum(1 for i in range(max_len) if i < len(a) and i < len(b) and a[i] == b[i])
    return matches / max_len


# ============ TÍNH ĐỘ CHÍNH XÁC (từ video-process.ipynb) ============

def compute_track_stats(char_votes: dict, char_confs: dict) -> list:
    """Tính winner/runner-up/margin/char_confidence cho từng vị trí ký tự.
   char_votes: {position: {char: vote_count}}
    char_confs: {position: {char: sum_of_confidences}}
    Trả về list stats theo thứ tự position."""
    stats = []
    for pos in sorted(char_votes.keys()):
        votes = char_votes[pos]
        confs = char_confs[pos]
        total_votes = sum(votes.values())
        sorted_chars = sorted(votes.items(), key=lambda x: x[1], reverse=True)

        winner_char, winner_votes = sorted_chars[0]
        runner_up_char, runner_up_votes = (
            sorted_chars[1] if len(sorted_chars) > 1 else (None, 0)
        )

        margin = (winner_votes - runner_up_votes) / total_votes if total_votes > 0 else 0
        winner_avg_conf = confs[winner_char] / winner_votes if winner_votes > 0 else 0
        char_confidence = margin * winner_avg_conf

        stats.append({
            'position': pos,
            'winner_char': winner_char,
            'winner_votes': winner_votes,
            'winner_avg_conf': winner_avg_conf,
            'runner_up_char': runner_up_char,
            'runner_up_votes': runner_up_votes,
            'total_votes': total_votes,
            'margin': margin,
            'char_confidence': char_confidence
        })
    return stats


def compute_plate_confidence(stats: list) -> float:
    """Geometric Mean của char_confidence → tin cậy cả biển số.
    Công thức từ video-process.ipynb: (∏ char_confidence[i]) ^ (1/n)
    Trả về giá trị 0.0 - 1.0 (chưa × 100)."""
    if not stats:
        return 0.0
    product = 1.0
    for s in stats:
        product *= max(s['char_confidence'], 1e-6)
    n = len(stats)
    return product ** (1.0 / n)


def build_text_from_stats(stats: list) -> str:
    """Ghép text từ winner_char của mỗi position."""
    return ''.join(s['winner_char'] for s in stats)


def build_alt_text_from_stats(stats: list, alt_position: int) -> str:
    """Ghép text, thay thế ký tự ở alt_position bằng runner_up_char."""
    chars = []
    for s in stats:
        if s['position'] == alt_position and s['runner_up_char']:
            chars.append(s['runner_up_char'])
        else:
            chars.append(s['winner_char'])
    return ''.join(chars)


def compute_alt_plate_confidence(stats: list, alt_position: int) -> float:
    """Geometric mean với alt_position dùng runner_up thay vì winner.
    Công thức từ video-process.ipynb."""
    if not stats:
        return 0.0
    product = 1.0
    for s in stats:
        if s['position'] == alt_position and s['winner_votes'] > 0:
            alt_conf = s['char_confidence'] * (s['runner_up_votes'] / s['winner_votes'])
            term = alt_conf
        else:
            term = s['char_confidence']
        product *= max(term, 1e-6)
    n = len(stats)
    return product ** (1.0 / n)


def compute_best_alt(stats: list) -> tuple:
    """Tìm bản alt tốt nhất (text, confidence) từ runner-up characters.
    Trả về: (alt_text, alt_confidence, alt_position) hoặc (None, 0.0, -1) nếu không có."""
    if not stats:
        return None, 0.0, -1

    best_text = None
    best_conf = 0.0
    best_pos = -1

    for s in stats:
        if s['runner_up_char'] and s['winner_votes'] > 0:
            alt_text = build_alt_text_from_stats(stats, s['position'])
            alt_conf = compute_alt_plate_confidence(stats, s['position'])
            if alt_conf > best_conf:
                best_conf = alt_conf
                best_text = alt_text
                best_pos = s['position']

    return best_text, best_conf, best_pos


def edit_distance(s1: str, s2: str) -> int:
    """Tính khoảng cách edit giữa 2 chuỗi."""
    if len(s1) < len(s2):
        return edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


class PlateTrack:
    """Một track đơn lẻ biển số, lưu lịch sử centroid và votes từng vị trí ký tự."""

    def __init__(self, track_id: int, centroid: tuple, plate_text: str, bbox: list = None, char_confs: list = None):
        self.track_id = track_id
        self.centroid = centroid
        self.plate_text = plate_text
        self.last_bbox = bbox
        self.miss_count = 0
        self.hit_count = 1
        self.created_at = time.time()
        self.first_frame = 0    # frame index khi detect lần đầu
        self.last_frame = 0     # frame index khi detect lần cuối

        # Character voting: {position: {char: vote_count}}
        self.char_votes = defaultdict(lambda: defaultdict(int))
        # Character confidences: {position: {char: sum_of_confs}}
        self.char_confs = defaultdict(lambda: defaultdict(float))
        self._init_votes(plate_text, char_confs)

    def _init_votes(self, text: str, char_confs: list = None):
        """Khởi tạo votes từ text đầu tiên."""
        for i, ch in enumerate(text):
            self.char_votes[i][ch] += 1
            if char_confs and i < len(char_confs):
                self.char_confs[i][ch] += char_confs[i]

    def update(self, centroid: tuple, plate_text: str, char_confs: list = None, bbox: list = None, frame_idx: int = 0):
        """Cập nhật track với detection mới."""
        self.centroid = centroid
        self.miss_count = 0
        self.hit_count += 1
        self.plate_text = plate_text
        self.last_frame = frame_idx
        if bbox:
            self.last_bbox = bbox

        for i, ch in enumerate(plate_text):
            self.char_votes[i][ch] += 1
            if char_confs and i < len(char_confs):
                self.char_confs[i][ch] += char_confs[i]

    def miss(self):
        """Gọi khi không detect được trong frame này."""
        self.miss_count += 1

    def get_voted_text(self) -> str:
        """Gộp kết quả voting từng vị trí ký tự, chọn ký tự có nhiều phiếu nhất."""
        if not self.char_votes:
            return self.plate_text

        result = []
        for pos in sorted(self.char_votes.keys()):
            votes = self.char_votes[pos]
            best_char = max(votes, key=votes.get)
            result.append(best_char)
        return ''.join(result)

    def get_confidence(self) -> float:
        """Tính confidence bằng Geometric Mean (như notebook video-process.ipynb)."""
        stats = compute_track_stats(self.char_votes, self.char_confs)
        return compute_plate_confidence(stats)

    def is_finalized(self) -> bool:
        """Track đã sẵn sàng finalize (đủ frame miss VÀ đủ hit)."""
        return self.miss_count >= MISS_THRESHOLD and self.hit_count >= MIN_HITS


class CentroidTracker:
    """Theo dõi detection qua frame bằng IOU + Centroid distance + Text similarity.
    Bao gồm finalized buffer để chống trùng lặp khi biển xuất hiện lại.
    Có merge buffer để gộp các track cùng text (từ video-process.ipynb)."""

    def __init__(self):
        self.tracks = {}  # {track_id: PlateTrack}
        self.next_id = 0
        self._finalized_buffer = []  # [(timestamp, bbox, text, conf, hit_count)]
        self._merge_buffer = {}  # {text: {char_votes, char_confs, bbox, snapshot, first_frame, last_frame, timestamp, total_hits}}
        self._frame_idx = 0  # frame counter

    def _cleanup_buffer(self):
        """Xóa các entry cũ hết TTL trong finalized buffer."""
        now = time.time()
        self._finalized_buffer = [
            entry for entry in self._finalized_buffer
            if now - entry[0] < FINALIZED_BUFFER_TTL
        ]

    def _match_against_buffer(self, det_bbox, det_text) -> bool:
        """Kiểm tra detection có match với track vừa finalize gần đây không.
        Nếu match → skip detection này (đã có trong DB rồi)."""
        if not self._finalized_buffer:
            return False

        for _, buf_bbox, buf_text, _, _ in self._finalized_buffer:
            iou = _compute_iou(det_bbox, buf_bbox) if det_bbox and buf_bbox else 0.0
            text_sim = _compute_text_similarity(det_text, buf_text)

            # Match nếu IOU cao HOẶC text giống nhau
            if iou >= IOU_THRESHOLD or text_sim >= 0.8:
                return True

        return False

    def update(self, detections: list, frame_idx: int = 0) -> list:
        """Cập nhật tracker với danh sách detection mới.
        detections: [{'bbox': [x1,y1,x2,y2], 'text': str, 'conf': float}]
        frame_idx: index frame hiện tại (dùng cho track frame range)
        Trả về danh sách tracks đã merge (sẵn sàng lưu DB)."""
        finalized = []
        self._cleanup_buffer()
        self._cleanup_merge_buffer()
        self._frame_idx = frame_idx

        # Tính centroid cho mỗi detection
        det_centroids = []
        for det in detections:
            bbox = det['bbox']
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            det_centroids.append(((cx, cy), det))

        # Match detection với track hiện tại bằng IOU + Centroid + Text
        matched_det = set()
        matched_track = set()

        for det_idx, (det_cent, det_info) in enumerate(det_centroids):
            best_score = -1
            best_track_id = None

            det_bbox = det_info.get('bbox')
            det_text = det_info.get('text', '')

            # Kiểm tra finalized buffer — nếu match với track vừa finalize → skip
            if self._match_against_buffer(det_bbox, det_text):
                matched_det.add(det_idx)
                continue

            for track_id, track in self.tracks.items():
                if track_id in matched_track:
                    continue

                # Tính IOU
                iou = _compute_iou(det_bbox, track.last_bbox) if det_bbox and track.last_bbox else 0.0

                # Tính centroid distance similarity
                cent_dist = np.sqrt(
                    (det_cent[0] - track.centroid[0]) ** 2 +
                    (det_cent[1] - track.centroid[1]) ** 2
                )
                cent_sim = max(0, 1.0 - (cent_dist / CENTROID_DISTANCE))

                # Tính text similarity
                track_text = track.get_voted_text()
                text_sim = _compute_text_similarity(det_text, track_text)

                # Điều kiện BẮT BUỘC: text phải giống nhau ít nhất 50%
                # Nếu text khác hoàn toàn → KHÔNG match → tạo track mới
                if text_sim < 0.5:
                    continue

                # Combined score: IOU 40% + Text 40% + Centroid 20%
                combined_score = iou * 0.4 + text_sim * 0.4 + cent_sim * 0.2

                # Match nếu IOU đủ cao HOẶC combined score đủ cao
                if iou >= IOU_THRESHOLD or combined_score >= MIN_MATCH_SCORE:
                    if combined_score > best_score:
                        best_score = combined_score
                        best_track_id = track_id

            if best_track_id is not None:
                self.tracks[best_track_id].update(
                    det_cent, det_info['text'],
                    char_confs=det_info.get('char_confs'),
                    bbox=det_info.get('bbox'),
                    frame_idx=frame_idx
                )
                matched_det.add(det_idx)
                matched_track.add(best_track_id)

        # Tạo track mới cho detection chưa match (và chưa bị skip bởi buffer)
        for det_idx, (det_cent, det_info) in enumerate(det_centroids):
            if det_idx not in matched_det:
                track = PlateTrack(
                    self.next_id, det_cent, det_info['text'],
                    bbox=det_info.get('bbox'),
                    char_confs=det_info.get('char_confs')
                )
                track.first_frame = frame_idx
                track.last_frame = frame_idx
                self.tracks[self.next_id] = track
                self.next_id += 1

        # Đánh dấu miss cho track không match
        for track_id in list(self.tracks.keys()):
            if track_id not in matched_track:
                self.tracks[track_id].miss()
                if self.tracks[track_id].is_finalized():
                    track = self.tracks[track_id]
                    final_text = track.get_voted_text()
                    final_conf = track.get_confidence()
                    format_score = get_plate_format_score(final_text)

                    # Tính alt_text + alt_confidence
                    stats = compute_track_stats(track.char_votes, track.char_confs)
                    alt_text, alt_conf, _ = compute_best_alt(stats)

                    # Merge vào merge buffer (gộp track cùng text)
                    merged = self._merge_into_buffer(
                        final_text, final_conf, alt_text, alt_conf,
                        track.char_votes, track.char_confs,
                        track.last_bbox, track.hit_count,
                        track.first_frame, track.last_frame
                    )
                    if merged:
                        finalized.append(merged)

                    # Thêm vào finalized buffer để chống duplicate
                    self._finalized_buffer.append((
                        time.time(),
                        track.last_bbox,
                        final_text,
                        final_conf,
                        track.hit_count
                    ))
                    # Giới hạn kích thước buffer
                    if len(self._finalized_buffer) > FINALIZED_BUFFER_MAX:
                        self._finalized_buffer = self._finalized_buffer[-FINALIZED_BUFFER_MAX:]

                    del self.tracks[track_id]

        return finalized

    def get_active_plates(self) -> list:
        """Lấy danh sách các biển đang được track (chưa finalize).
        Dùng để hiển thị realtime trên client."""
        active = []
        for track in self.tracks.values():
            if track.hit_count >= 1:
                text = track.get_voted_text()
                active.append({
                    'text': text,
                    'conf': track.get_confidence(),
                    'bbox': track.last_bbox,
                    'hit_count': track.hit_count
                })
        return active

    # ============ MERGE BUFFER (từ video-process.ipynb) ============

    def _merge_into_buffer(self, text, conf, alt_text, alt_conf,
                           char_votes, char_confs, bbox, hit_count,
                           first_frame, last_frame) -> dict:
        """Gộp track mới vào merge buffer. Nếu text trùng → combine votes.
        Nếu fuzzy match (edit_distance ≤ 1, gap ≤ 2s) → combine.
        Trả về dict kết quả nếu là lần merge đầu tiên (mới), None nếu đã có sẵn."""
        now = time.time()

        # Tìm match chính xác
        if text in self._merge_buffer:
            buf = self._merge_buffer[text]
            # Combine votes
            for pos, votes in char_votes.items():
                buf['char_votes'].setdefault(pos, defaultdict(int))
                for ch, cnt in votes.items():
                    buf['char_votes'][pos][ch] += cnt
            for pos, confs in char_confs.items():
                buf['char_confs'].setdefault(pos, defaultdict(float))
                for ch, c in confs.items():
                    buf['char_confs'][pos][ch] += c
            buf['total_hits'] += hit_count
            buf['first_frame'] = min(buf['first_frame'], first_frame)
            buf['last_frame'] = max(buf['last_frame'], last_frame)
            buf['timestamp'] = min(buf['timestamp'], now)
            # Cập nhật bbox mới nhất
            buf['bbox'] = bbox
            return None  # Đã merge, chưa flush

        # Fuzzy merge: edit_distance ≤ 1 + gap ≤ 2s
        for buf_text, buf in list(self._merge_buffer.items()):
            if abs(len(text) - len(buf_text)) <= 1:
                if edit_distance(text, buf_text) <= MERGE_EDIT_DISTANCE:
                    # Kiểm tra khoảng cách frame
                    gap_frames = max(0, max(first_frame, buf['first_frame']) -
                                     min(last_frame, buf['last_frame']))
                    # Ước tính gap_seconds từ frame gap (giả sử ~2 FPS)
                    gap_seconds = gap_frames * 0.5  # ~0.5s mỗi frame ở 2 FPS sampling
                    if gap_seconds <= MERGE_TIME_GAP:
                        # Merge text mới vào buffer cũ
                        for pos, votes in char_votes.items():
                            buf['char_votes'].setdefault(pos, defaultdict(int))
                            for ch, cnt in votes.items():
                                buf['char_votes'][pos][ch] += cnt
                        for pos, confs in char_confs.items():
                            buf['char_confs'].setdefault(pos, defaultdict(float))
                            for ch, c in confs.items():
                                buf['char_confs'][pos][ch] += c
                        buf['total_hits'] += hit_count
                        buf['first_frame'] = min(buf['first_frame'], first_frame)
                        buf['last_frame'] = max(buf['last_frame'], last_frame)
                        buf['timestamp'] = min(buf['timestamp'], now)
                        buf['bbox'] = bbox
                        return None  # Đã merge

        # Không match → tạo entry mới trong buffer
        self._merge_buffer[text] = {
            'text': text,
            'char_votes': {pos: dict(v) for pos, v in char_votes.items()},
            'char_confs': {pos: dict(c) for pos, c in char_confs.items()},
            'bbox': bbox,
            'first_frame': first_frame,
            'last_frame': last_frame,
            'timestamp': now,
            'total_hits': hit_count,
        }
        return {
            'text': text,
            'conf': conf,
            'alt_text': alt_text,
            'alt_confidence': alt_conf,
            'hit_count': hit_count,
            'bbox': bbox,
            'format_score': get_plate_format_score(text),
            'total_frames': hit_count,
            'frame_start': first_frame,
            'frame_end': last_frame,
        }

    def _cleanup_merge_buffer(self):
        """Xóa các entry cũ hết TTL trong merge buffer."""
        now = time.time()
        expired = [k for k, v in self._merge_buffer.items()
                   if now - v['timestamp'] > MERGE_BUFFER_TTL]
        for k in expired:
            del self._merge_buffer[k]

    def flush_merged(self) -> list:
        """Flush tất cả kết quả đã merge trong buffer. Gọi khi video kết thúc."""
        results = []
        for text, buf in self._merge_buffer.items():
            # Recompute confidence từ votes đã merge
            merged_stats = compute_track_stats(buf['char_votes'], buf['char_confs'])
            merged_conf = compute_plate_confidence(merged_stats)
            alt_text, alt_conf, _ = compute_best_alt(merged_stats)

            results.append({
                'text': text,
                'conf': merged_conf,
                'alt_text': alt_text,
                'alt_confidence': alt_conf,
                'hit_count': buf['total_hits'],
                'bbox': buf['bbox'],
                'format_score': get_plate_format_score(text),
                'total_frames': buf['total_hits'],
                'frame_start': buf['first_frame'],
                'frame_end': buf['last_frame'],
            })
        self._merge_buffer.clear()
        return results
