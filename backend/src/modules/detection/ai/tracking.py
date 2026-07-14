"""
Video Tracking: IOU + Centroid Matching + Character-level Voting.
"""
import time
import numpy as np
from collections import defaultdict
from src.modules.detection.ai.validation import get_plate_format_score

MISS_THRESHOLD = 4
MIN_HITS = 2
CENTROID_DISTANCE = 100
IOU_THRESHOLD = 0.3
MIN_MATCH_SCORE = 0.25
FINALIZED_BUFFER_TTL = 5.0
FINALIZED_BUFFER_MAX = 20
VOTE_MARGIN = 1.2
MERGE_BUFFER_TTL = 10.0
MERGE_EDIT_DISTANCE = 1
MERGE_TIME_GAP = 2.0

def _compute_iou(box_a, box_b) -> float:
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

def compute_track_stats(char_votes: dict, char_confs: dict) -> list:
    stats = []
    for pos in sorted(char_votes.keys()):
        votes = char_votes[pos]
        confs = char_confs[pos]
        total_votes = sum(votes.values())
        sorted_chars = sorted(votes.items(), key=lambda x: x[1], reverse=True)
        winner_char, winner_votes = sorted_chars[0]
        runner_up_char, runner_up_votes = (sorted_chars[1] if len(sorted_chars) > 1 else (None, 0))
        margin = (winner_votes - runner_up_votes) / total_votes if total_votes > 0 else 0
        winner_avg_conf = confs[winner_char] / winner_votes if winner_votes > 0 else 0
        char_confidence = margin * winner_avg_conf
        stats.append({
            'position': pos, 'winner_char': winner_char, 'winner_votes': winner_votes,
            'winner_avg_conf': winner_avg_conf, 'runner_up_char': runner_up_char,
            'runner_up_votes': runner_up_votes, 'total_votes': total_votes,
            'margin': margin, 'char_confidence': char_confidence
        })
    return stats

def compute_plate_confidence(stats: list) -> float:
    if not stats:
        return 0.0
    product = 1.0
    for s in stats:
        product *= max(s['char_confidence'], 1e-6)
    return product ** (1.0 / len(stats))

def build_text_from_stats(stats: list) -> str:
    return ''.join(s['winner_char'] for s in stats)

def build_alt_text_from_stats(stats: list, alt_position: int) -> str:
    chars = []
    for s in stats:
        if s['position'] == alt_position and s['runner_up_char']:
            chars.append(s['runner_up_char'])
        else:
            chars.append(s['winner_char'])
    return ''.join(chars)

def compute_alt_plate_confidence(stats: list, alt_position: int) -> float:
    if not stats:
        return 0.0
    product = 1.0
    for s in stats:
        if s['position'] == alt_position and s['winner_votes'] > 0:
            term = s['char_confidence'] * (s['runner_up_votes'] / s['winner_votes'])
        else:
            term = s['char_confidence']
        product *= max(term, 1e-6)
    return product ** (1.0 / len(stats))

def compute_best_alt(stats: list) -> tuple:
    if not stats:
        return None, 0.0, -1
    best_text, best_conf, best_pos = None, 0.0, -1
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
    def __init__(self, track_id, centroid, plate_text, bbox=None, char_confs=None):
        self.track_id = track_id
        self.centroid = centroid
        self.plate_text = plate_text
        self.first_bbox = bbox       # bbox của frame đầu tiên phát hiện
        self.last_bbox = bbox        # bbox của frame cuối cùng (cập nhật mỗi frame)
        self.miss_count = 0
        self.hit_count = 1
        self.created_at = time.time()
        self.first_frame = 0
        self.last_frame = 0
        self.first_frame_img = None  # ảnh PIL frame đầu tiên
        self.best_frame_img = None
        self.best_frame_conf = 0.0
        self.char_votes = defaultdict(lambda: defaultdict(int))
        self.char_confs = defaultdict(lambda: defaultdict(float))
        self._init_votes(plate_text, char_confs)

    def _init_votes(self, text, char_confs=None):
        for i, ch in enumerate(text):
            self.char_votes[i][ch] += 1
            if char_confs and i < len(char_confs):
                self.char_confs[i][ch] += char_confs[i]

    def update(self, centroid, plate_text, char_confs=None, bbox=None, frame_idx=0, plate_conf=0.0, frame_img=None):
        self.centroid = centroid
        self.miss_count = 0
        self.hit_count += 1
        self.plate_text = plate_text
        self.last_frame = frame_idx
        if bbox:
            self.last_bbox = bbox
        if self.first_frame_img is None and frame_img is not None:
            self.first_frame_img = frame_img
        if frame_img is not None and plate_conf > self.best_frame_conf:
            self.best_frame_conf = plate_conf
            self.best_frame_img = frame_img
        for i, ch in enumerate(plate_text):
            self.char_votes[i][ch] += 1
            if char_confs and i < len(char_confs):
                self.char_confs[i][ch] += char_confs[i]

    def miss(self):
        self.miss_count += 1

    def get_voted_text(self) -> str:
        if not self.char_votes:
            return self.plate_text
        result = []
        for pos in sorted(self.char_votes.keys()):
            votes = self.char_votes[pos]
            best_char = max(votes, key=votes.get)
            result.append(best_char)
        return ''.join(result)

    def get_confidence(self) -> float:
        stats = compute_track_stats(self.char_votes, self.char_confs)
        return compute_plate_confidence(stats)

    def is_finalized(self) -> bool:
        return self.miss_count >= MISS_THRESHOLD and self.hit_count >= MIN_HITS

class CentroidTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 0
        self._finalized_buffer = []
        self._merge_buffer = {}
        self._frame_idx = 0

    def _cleanup_buffer(self):
        now = time.time()
        self._finalized_buffer = [e for e in self._finalized_buffer if now - e[0] < FINALIZED_BUFFER_TTL]

    def _match_against_buffer(self, det_bbox, det_text) -> bool:
        if not self._finalized_buffer:
            return False
        for _, buf_bbox, buf_text, _, _ in self._finalized_buffer:
            iou = _compute_iou(det_bbox, buf_bbox) if det_bbox and buf_bbox else 0.0
            text_sim = _compute_text_similarity(det_text, buf_text)
            if iou >= IOU_THRESHOLD or text_sim >= 0.8:
                return True
        return False

    def update(self, detections, frame_idx=0, frame_img=None) -> list:
        finalized = []
        self._cleanup_buffer()
        self._cleanup_merge_buffer()
        self._frame_idx = frame_idx

        det_centroids = []
        for det in detections:
            bbox = det['bbox']
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            det_centroids.append(((cx, cy), det))

        matched_det = set()
        matched_track = set()

        for det_idx, (det_cent, det_info) in enumerate(det_centroids):
            best_score = -1
            best_track_id = None
            det_bbox = det_info.get('bbox')
            det_text = det_info.get('text', '')

            if self._match_against_buffer(det_bbox, det_text):
                matched_det.add(det_idx)
                continue

            for track_id, track in self.tracks.items():
                if track_id in matched_track:
                    continue
                iou = _compute_iou(det_bbox, track.last_bbox) if det_bbox and track.last_bbox else 0.0
                cent_dist = np.sqrt((det_cent[0] - track.centroid[0])**2 + (det_cent[1] - track.centroid[1])**2)
                cent_sim = max(0, 1.0 - (cent_dist / CENTROID_DISTANCE))
                track_text = track.get_voted_text()
                text_sim = _compute_text_similarity(det_text, track_text)
                if text_sim < 0.5:
                    continue
                combined_score = iou * 0.4 + text_sim * 0.4 + cent_sim * 0.2
                if iou >= IOU_THRESHOLD or combined_score >= MIN_MATCH_SCORE:
                    if combined_score > best_score:
                        best_score = combined_score
                        best_track_id = track_id

            if best_track_id is not None:
                self.tracks[best_track_id].update(
                    det_cent, det_info['text'], char_confs=det_info.get('char_confs'),
                    bbox=det_info.get('bbox'), frame_idx=frame_idx,
                    plate_conf=det_info.get('conf', 0.0), frame_img=frame_img
                )
                matched_det.add(det_idx)
                matched_track.add(best_track_id)

        for det_idx, (det_cent, det_info) in enumerate(det_centroids):
            if det_idx not in matched_det:
                track = PlateTrack(self.next_id, det_cent, det_info['text'],
                    bbox=det_info.get('bbox'), char_confs=det_info.get('char_confs'))
                track.first_frame = frame_idx
                track.last_frame = frame_idx
                track.first_frame_img = frame_img          # ảnh frame đầu tiên phát hiện
                track.best_frame_conf = det_info.get('conf', 0.0)
                track.best_frame_img = frame_img
                self.tracks[self.next_id] = track
                self.next_id += 1

        for track_id in list(self.tracks.keys()):
            if track_id not in matched_track:
                self.tracks[track_id].miss()
                if self.tracks[track_id].is_finalized():
                    track = self.tracks[track_id]
                    final_text = track.get_voted_text()
                    final_conf = track.get_confidence()
                    stats = compute_track_stats(track.char_votes, track.char_confs)
                    alt_text, alt_conf, _ = compute_best_alt(stats)
                    merged = self._merge_into_buffer(
                        final_text, final_conf, alt_text, alt_conf,
                        track.char_votes, track.char_confs,
                        track.first_bbox, track.last_bbox, track.hit_count,
                        track.first_frame, track.last_frame,
                        track.first_frame_img, track.best_frame_img, track.best_frame_conf
                    )
                    if merged:
                        finalized.append(merged)
                    self._finalized_buffer.append((time.time(), track.last_bbox, final_text, final_conf, track.hit_count))
                    if len(self._finalized_buffer) > FINALIZED_BUFFER_MAX:
                        self._finalized_buffer = self._finalized_buffer[-FINALIZED_BUFFER_MAX:]
                    del self.tracks[track_id]
        return finalized

    def get_active_plates(self) -> list:
        """Trả về danh sách biển đang track — KHÔNG tính confidence (chỉ cần text + bbox để hiển thị live).
        Confidence chỉ được tính khi finalize (biển biến mất)."""
        active = []
        for track in self.tracks.values():
            if track.hit_count >= 1:
                text = track.get_voted_text()
                active.append({'text': text, 'conf': 0, 'bbox': track.last_bbox, 'hit_count': track.hit_count})
        return active

    def _merge_into_buffer(self, text, conf, alt_text, alt_conf, char_votes, char_confs, first_bbox, last_bbox, hit_count,
                           first_frame, last_frame, first_frame_img=None, best_frame_img=None, best_frame_conf=0.0) -> dict:
        now = time.time()
        if text in self._merge_buffer:
            buf = self._merge_buffer[text]
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
            # Giữ first_bbox từ track sớm nhất, KHÔNG ghi đè
            buf['bbox'] = last_bbox  # bbox mới nhất cho active tracking
            if best_frame_conf > buf.get('best_frame_conf', 0):
                buf['best_frame_img'] = best_frame_img
                buf['best_frame_conf'] = best_frame_conf
            return None

        for buf_text, buf in list(self._merge_buffer.items()):
            if abs(len(text) - len(buf_text)) <= 1:
                if edit_distance(text, buf_text) <= MERGE_EDIT_DISTANCE:
                    gap_frames = max(0, max(first_frame, buf['first_frame']) - min(last_frame, buf['last_frame']))
                    gap_seconds = gap_frames * 0.5
                    if gap_seconds <= MERGE_TIME_GAP:
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
                        # Giữ first_bbox từ track sớm nhất, KHÔNG ghi đè
                        buf['bbox'] = last_bbox  # bbox mới nhất cho active tracking
                        if best_frame_conf > buf.get('best_frame_conf', 0):
                            buf['best_frame_img'] = best_frame_img
                            buf['best_frame_conf'] = best_frame_conf
                        return None

        self._merge_buffer[text] = {
            'text': text, 'char_votes': {pos: dict(v) for pos, v in char_votes.items()},
            'char_confs': {pos: dict(c) for pos, c in char_confs.items()},
            'first_bbox': first_bbox, 'bbox': last_bbox,
            'first_frame': first_frame, 'last_frame': last_frame,
            'timestamp': now, 'total_hits': hit_count, 'first_frame_img': first_frame_img,
            'best_frame_img': best_frame_img, 'best_frame_conf': best_frame_conf,
            '_already_returned': True,  # Đánh dấu đã return → flush_merged sẽ skip
        }
        return {
            'text': text, 'conf': conf, 'alt_text': alt_text, 'alt_confidence': alt_conf,
            'hit_count': hit_count, 'first_bbox': first_bbox, 'bbox': last_bbox,
            'format_score': get_plate_format_score(text),
            'total_frames': hit_count, 'frame_start': first_frame, 'frame_end': last_frame,
            'first_frame_img': first_frame_img, 'best_frame_img': best_frame_img,
        }

    def _cleanup_merge_buffer(self):
        now = time.time()
        expired = [k for k, v in self._merge_buffer.items() if now - v['timestamp'] > MERGE_BUFFER_TTL]
        for k in expired:
            del self._merge_buffer[k]

    def flush_merged(self) -> list:
        results = []
        for text, buf in self._merge_buffer.items():
            # Skip entry đã được return trong _merge_into_buffer (tránh duplicate DB save)
            if buf.get('_already_returned'):
                continue
            merged_stats = compute_track_stats(buf['char_votes'], buf['char_confs'])
            merged_conf = compute_plate_confidence(merged_stats)
            alt_text, alt_conf, _ = compute_best_alt(merged_stats)
            results.append({
                'text': text, 'conf': merged_conf, 'alt_text': alt_text, 'alt_confidence': alt_conf,
                'hit_count': buf['total_hits'], 'first_bbox': buf.get('first_bbox'), 'bbox': buf['bbox'],
                'format_score': get_plate_format_score(text),
                'total_frames': buf['total_hits'], 'frame_start': buf['first_frame'],
                'frame_end': buf['last_frame'], 'first_frame_img': buf.get('first_frame_img'),
                'best_frame_img': buf.get('best_frame_img'),
            })
        self._merge_buffer.clear()
        return results
