import os
import cv2
import shutil
import tempfile
import numpy as np
import uuid
import threading
import time
import base64
import asyncio
import traceback
import subprocess
import json
import torch
from datetime import datetime
from PIL import Image
from fastapi import UploadFile, BackgroundTasks, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from src.core.config.settings import settings
from src.core.config.database import SessionLocal
from src.modules.detection.models import Detection, VideoJob
from src.modules.region.models import Region
from src.modules.detection.ai.pipeline import init_lpr_service, draw_plate_results
from src.modules.detection.ai.tracking import CentroidTracker
from src.modules.detection.ai.validation import is_valid_plate, get_plate_format_score
from src.core.utils.helpers import save_snapshot_image, save_snapshot_local_only, batch_upload_to_cloudinary, update_detection_paths_to_cloudinary, cleanup_file, log_activity, get_vietnam_now

# Lưu trữ trạng thái video task cũ dùng UUID
tasks_db = {}

# Preview frame + cancel flag cho video processing
_preview_frames = {}   # task_id (int) -> bytes (JPEG)
_cancel_flags = {}     # task_id (int) -> bool

def _safe_write_frame(writer, frame, frame_idx, writer_enabled, output_path, fps, width, height):
    """Ghi frame vào output video một cách an toàn.
    Trả về (writer, writer_enabled, new_output_path): writer có thể thay đổi nếu recovery,
    new_output_path khác None nếu output file thay đổi."""
    if not writer_enabled or writer is None:
        return writer, writer_enabled, None

    try:
        ret = writer.write(frame)
        return writer, writer_enabled, None
    except Exception as e:
        pass  # Recovery bên dưới

        try:
            if writer:
                writer.release()
        except Exception:
            pass

        # Recovery: tạo file mới với mp4v (KHÔNG ghi đè lên file corrupted)
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            output_path_mp4 = os.path.splitext(output_path)[0] + '_recovery.mp4'
            new_writer = cv2.VideoWriter(output_path_mp4, fourcc, fps, (width, height))
            if new_writer.isOpened():
                try:
                    new_writer.write(frame)
                    return new_writer, True, output_path_mp4
                except Exception:
                    new_writer.release()
        except Exception:
            pass
        return None, False, None


# =============================================================================
# FFmpeg helpers — giải pháp đáng tin cậy cho mọi codec video
# =============================================================================

def _check_ffmpeg():
    """Kiểm tra ffmpeg có sẵn trong hệ thống không."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_video_info_ffmpeg(input_path):
    """Lấy thông tin video bằng ffprobe (width, height, fps, total_frames, duration)."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise Exception(f"ffprobe không thể đọc video: {result.stderr}")

    info = json.loads(result.stdout)

    # Tìm video stream
    video_stream = None
    for stream in info.get('streams', []):
        if stream.get('codec_type') == 'video':
            video_stream = stream
            break

    if not video_stream:
        raise Exception("Không tìm thấy video stream trong file.")

    # Parse FPS (vd: "30/1" hoặc "30000/1001")
    fps_str = video_stream.get('r_frame_rate', '30/1')
    if '/' in fps_str:
        num, den = map(int, fps_str.split('/'))
        fps = num / den if den > 0 else 30.0
    else:
        fps = float(fps_str)

    width = int(video_stream.get('width', 640))
    height = int(video_stream.get('height', 480))

    # Tổng số frame
    total_frames = int(video_stream.get('nb_frames', 0))
    duration = float(info.get('format', {}).get('duration', 0))

    if total_frames <= 0 and duration > 0:
        total_frames = int(duration * fps)

    return {
        'width': width,
        'height': height,
        'fps': fps,
        'total_frames': total_frames,
        'duration': duration
    }


def _process_video_ffmpeg(job_id: int, input_path: str, output_path: str, filename: str,
                          user_id: int | None = None, region_id: int | None = None):
    """Xử lý video bằng ffmpeg subprocess — đáng tin cậy với mọi codec đầu vào.
    Đọc: ffmpeg pipe rawvideo → Python xử lý → ghi: ffmpeg pipe H.264 MP4."""
    reader_proc = None
    writer_proc = None
    pil_img = None

    try:
        # ── Lấy thông tin video bằng ffprobe ──
        info = _get_video_info_ffmpeg(input_path)
        width = info['width']
        height = info['height']
        fps = info['fps']
        total_frames = info['total_frames']
        duration = info['duration']
        file_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0

        print(f"[LPR] {filename} | {width}x{height} {fps:.0f}fps | {duration:.0f}s | {file_size // (1024*1024)}MB | ffmpeg")

        # ── Kiểm tra dung lượng ổ đĩa ──
        temp_dir = tempfile.gettempdir()
        try:
            disk_usage = shutil.disk_usage(temp_dir)
            free_mb = disk_usage.free // (1024 * 1024)
            if free_mb < 500:
                raise Exception(f"Không đủ dung lượng ổ đĩa: chỉ còn {free_mb}MB trống.")
        except Exception as disk_err:
            if "Không đủ dung lượng" in str(disk_err):
                raise

        # ── Cập nhật job status ──
        with SessionLocal() as db:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "processing"
                job.total_frames = total_frames
                job.fps = fps
                job.duration = duration
                job.file_size = file_size
                db.commit()

        # ── Tạo ffmpeg reader (decode ANY codec → raw BGR24) ──
        reader_cmd = [
            'ffmpeg', '-v', 'error',
            '-i', input_path,
            '-f', 'rawvideo', '-pix_fmt', 'bgr24',
            '-'
        ]
        reader_proc = subprocess.Popen(reader_cmd, stdout=subprocess.PIPE)

        # ── Tạo ffmpeg writer (H.264 MP4 — chuẩn, đáng tin cậy) ──
        output_mp4 = os.path.splitext(output_path)[0] + '.mp4'
        writer_cmd = [
            'ffmpeg', '-y', '-v', 'error',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24',
            '-s', f'{width}x{height}',
            '-r', str(fps),
            '-i', '-',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            output_mp4
        ]
        writer_proc = subprocess.Popen(writer_cmd, stdin=subprocess.PIPE)
        output_path = output_mp4

        # ── Xử lý frame ──
        frame_size = width * height * 3
        font = cv2.FONT_HERSHEY_SIMPLEX
        frame_idx = 0
        processed_count = 0
        written_count = 0
        start_time = time.time()
        first_inference_done = False

        run_inference = init_lpr_service()
        centroid_tracker = CentroidTracker()
        local_snapshot_paths = []

        target_fps = 2
        frame_skip = max(1, int(fps / target_fps))
        stage1_imgsz = 1024

        last_plates = []
        last_plates_frame = -999
        PLATE_DISPLAY_FRAMES = max(1, int(fps * 0.5))

        # Màu viền BGR cho mỗi plate (đủ sáng để nổi bật trên mọi nền)
        _BOX_COLORS = [
            (0, 255, 255),    # Vàng
            (255, 128, 0),    # Xanh dương đậm
            (0, 255, 0),      # Xanh lá
            (255, 0, 255),    # Tím
            (255, 255, 0),    # Cyan
        ]

        def draw_boxes_on_frame(frame, plates):
            h_frame, w_frame = frame.shape[:2]
            for i, plate in enumerate(plates):
                x1, y1, x2, y2 = plate['bbox']
                if x2 <= x1 or y2 <= y1:
                    continue
                plate_text = plate.get('plate_text') or plate.get('text', '')
                plate_conf = plate.get('plate_confidence') or plate.get('conf', 0)
                label = f"{plate_text} {plate_conf:.2%}" if plate_conf else plate_text

                color = _BOX_COLORS[i % len(_BOX_COLORS)]

                # Viền dày, nổi bật
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

                # Nền chữ + chữ đen
                font_scale = 0.7
                thickness = 2
                (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
                label_y1 = max(0, y1 - th - 10)
                label_y2 = y1
                label_x2 = min(w_frame, x1 + tw + 6)
                cv2.rectangle(frame, (x1, label_y1), (label_x2, label_y2), color, -1)
                cv2.putText(frame, label, (x1 + 3, label_y2 - 4), font, font_scale, (0, 0, 0), thickness)

        while True:
            # ── Kiểm tra tín hiệu dừng ──
            if _cancel_flags.pop(job_id, False):
                print(f"[LPR] Job {job_id} cancelled by user at frame {frame_idx}")
                break

            # Đọc frame từ ffmpeg pipe
            raw = reader_proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break

            # .copy() — np.frombuffer từ bytes tạo array read-only,
            # cv2.rectangle cần ghi nên bắt buộc copy sang writable array
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()

            try:
                if frame is None or frame.size == 0:
                    frame_idx += 1
                    continue

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                # Frame skip — giữ nguyên frame gốc, chỉ bỏ qua inference
                if frame_idx % frame_skip != 0:
                    if last_plates and (frame_idx - last_plates_frame) <= PLATE_DISPLAY_FRAMES:
                        draw_boxes_on_frame(frame, last_plates)
                    try:
                        writer_proc.stdin.write(frame.tobytes())
                        written_count += 1
                    except BrokenPipeError:
                        print("[WARN] ffmpeg writer pipe broken")
                    frame_idx += 1
                    continue

                # ── Chạy inference ──
                plates = []
                try:
                    plates = run_inference(
                        pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID,
                        settings.CONF_S3_VID, "video", imgsz=stage1_imgsz
                    )
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    try:
                        plates = run_inference(
                            pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID,
                            settings.CONF_S3_VID, "video", imgsz=stage1_imgsz
                        )
                    except Exception:
                        plates = []
                    torch.cuda.empty_cache()
                except Exception as e:
                    plates = []

                if not first_inference_done:
                    first_inference_done = True

                # Vẽ TẤT CẢ plates lên frame (bao gồm cả "???" và chưa valid)
                if plates:
                    last_plates = plates
                    last_plates_frame = frame_idx

                draw_boxes_on_frame(frame, plates)

                # ── Lưu preview frame (JPEG) cho frontend ──
                try:
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    _preview_frames[job_id] = jpeg.tobytes()
                except Exception:
                    pass

                # ── Centroid tracking (chỉ với plate hợp lệ) ──
                valid_plates = []
                for plate in plates:
                    plate_text = plate.get('plate_text') or plate.get('text', '')
                    if not plate_text or plate_text == "???" or "?" in plate_text:
                        continue
                    if not is_valid_plate(plate_text):
                        continue
                    if get_plate_format_score(plate_text) <= 0:
                        continue
                    # Normalize keys cho centroid tracker (expects 'text'/'conf'/'char_confs')
                    valid_plates.append({
                        'text': plate_text,
                        'conf': plate.get('plate_confidence') or plate.get('conf', 0),
                        'bbox': plate['bbox'],
                        'char_confs': plate.get('char_confs'),
                    })

                finalized = centroid_tracker.update(valid_plates, frame_idx=frame_idx, frame_img=pil_img)

                for result in finalized:
                    try:
                        final_text = result['text']
                        final_conf = result['conf']
                        # Ưu tiên first_bbox (frame đầu tiên detect) để ảnh snapshot nhất quán
                        final_bbox = result.get('first_bbox') or result.get('bbox')
                        format_score = result.get('format_score', 0)
                        if not is_valid_plate(final_text) or format_score <= 0:
                            continue
                        first_img = result.get('first_frame_img') or result.get('best_frame_img') or pil_img
                        if final_bbox:
                            annotated_img = draw_plate_results(first_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                        else:
                            annotated_img = draw_plate_results(first_img, [{'bbox': [0, 0, 100, 100], 'text': final_text, 'conf': final_conf}])
                        snapshot_rel_path = save_snapshot_local_only(annotated_img)
                        local_snapshot_paths.append(snapshot_rel_path)
                        with SessionLocal() as db:
                            db_item = Detection(
                                plate_text=final_text, plate_confidence=final_conf,
                                alt_text=result.get('alt_text'), alt_confidence=result.get('alt_confidence'),
                                total_frames=result.get('total_frames', 0),
                                frame_start=result.get('frame_start'), frame_end=result.get('frame_end'),
                                image_path=snapshot_rel_path, source_type="video",
                                video_job_id=job_id, user_id=user_id, region_id=region_id
                            )
                            db.add(db_item)
                            db.commit()
                    except Exception:
                        pass

                # ── Ghi frame (đã vẽ bounding box) ──
                try:
                    writer_proc.stdin.write(frame.tobytes())
                    written_count += 1
                except BrokenPipeError:
                    print("[WARN] ffmpeg writer pipe broken")

                frame_idx += 1
                processed_count += 1

                # ── Cập nhật progress ──
                if processed_count % 2 == 0 or frame_idx >= total_frames:
                    elapsed = time.time() - start_time
                    raw_fps = frame_idx / elapsed if elapsed > 0 else 0.0
                    pct = int((frame_idx / total_frames) * 100) if total_frames > 0 else 0
                    try:
                        with SessionLocal() as db:
                            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
                            if job:
                                job.progress = pct
                                job.fps = round(raw_fps, 1)
                                job.current_frame = frame_idx
                                db.commit()
                    except Exception:
                        pass

                    if processed_count % 20 == 0 and torch.cuda.is_available():
                        torch.cuda.empty_cache()

            except Exception as frame_err:
                if processed_count < 3:
                    print(f"[ERROR] Frame {frame_idx}: {type(frame_err).__name__}: {frame_err}")
                # Luôn ghi frame vào output dù inference fail (không được drop frame)
                try:
                    writer_proc.stdin.write(frame.tobytes())
                    written_count += 1
                except BrokenPipeError:
                    pass
                except Exception:
                    pass
                frame_idx += 1
                processed_count += 1
                continue

        # ── Đóng ffmpeg processes ──
        if reader_proc:
            try:
                reader_proc.stdout.close()
                reader_proc.wait(timeout=30)
            except Exception:
                reader_proc.kill()
        if writer_proc:
            try:
                writer_proc.stdin.close()
                writer_proc.wait(timeout=60)
            except Exception:
                writer_proc.kill()

        reader_proc = None
        writer_proc = None

        cleanup_file(input_path)

        # ── Flush merged results từ centroid tracker ──
        merged_results = centroid_tracker.flush_merged()
        for result in merged_results:
            try:
                final_text = result['text']
                final_conf = result['conf']
                # Ưu tiên first_bbox (frame đầu tiên detect) để ảnh snapshot nhất quán
                final_bbox = result.get('first_bbox') or result.get('bbox')
                format_score = result.get('format_score', 0)

                if not is_valid_plate(final_text):
                    continue
                if format_score <= 0:
                    continue

                first_img = result.get('first_frame_img') or result.get('best_frame_img')

                try:
                    if final_bbox and first_img:
                        annotated_img = draw_plate_results(first_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    elif final_bbox and pil_img:
                        annotated_img = draw_plate_results(pil_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    else:
                        from PIL import Image as PILImage
                        annotated_img = PILImage.new('RGB', (640, 480), color=(0, 0, 0))
                except Exception:
                    from PIL import Image as PILImage
                    annotated_img = PILImage.new('RGB', (640, 480), color=(0, 0, 0))

                snapshot_rel_path = save_snapshot_local_only(annotated_img)
                local_snapshot_paths.append(snapshot_rel_path)

                with SessionLocal() as db:
                    db_item = Detection(
                        plate_text=final_text,
                        plate_confidence=final_conf,
                        alt_text=result.get('alt_text'),
                        alt_confidence=result.get('alt_confidence'),
                        total_frames=result.get('total_frames', 0),
                        frame_start=result.get('frame_start'),
                        frame_end=result.get('frame_end'),
                        image_path=snapshot_rel_path,
                        source_type="video",
                        video_job_id=job_id,
                        user_id=user_id,
                        region_id=region_id
                    )
                    db.add(db_item)
                    db.commit()
            except Exception:
                pass

        # ── Hoàn thành ──
        with SessionLocal() as db:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.progress = 100
                job.current_frame = total_frames
                job.completed_at = get_vietnam_now()
                if os.path.exists(output_path):
                    job.output_video = output_path
                else:
                    job.output_video = None
                db.commit()

        elapsed = time.time() - start_time
        print(f"[LPR] ✅ Done: {written_count}/{frame_idx} frames | {elapsed:.0f}s | {output_path}")

        # ── Batch upload snapshots lên Cloudinary sau khi xử lý xong ──
        if local_snapshot_paths:
            try:
                cloud_mapping = batch_upload_to_cloudinary(local_snapshot_paths)
                if cloud_mapping:
                    update_detection_paths_to_cloudinary(cloud_mapping)
            except Exception as e:
                print(f"[BATCH-UPLOAD] Loi batch upload: {e}")
            # Xóa các file local còn lại (failed upload hoặc không có Cloudinary)
            for p in local_snapshot_paths:
                cleanup_file(p)

        # ── Dọn dẹp in-memory state ──
        _preview_frames.pop(job_id, None)
        _cancel_flags.pop(job_id, None)

    except Exception as e:
        print(f"[ERROR] Video FAILED at frame {frame_idx}/{total_frames}: {type(e).__name__}: {e}")

        # Cleanup ffmpeg processes
        for proc in [reader_proc, writer_proc]:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass

        cleanup_file(input_path)
        cleanup_file(output_path)
        cleanup_file(os.path.splitext(output_path)[0] + '.mp4')

        error_detail = f"{type(e).__name__}: {e}"
        if "CUDA" in str(e) or "out of memory" in str(e).lower():
            error_detail = f"GPU hết bộ nhớ (CUDA OOM): {e}"
        elif "No space left" in str(e) or "disk" in str(e).lower():
            error_detail = f"Không đủ dung lượng ổ đĩa: {e}"

        with SessionLocal() as db:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = error_detail
                db.commit()


# =============================================================================
# Fallback: OpenCV VideoWriter (khi không có ffmpeg)
# =============================================================================

def _process_video_opencv(job_id: int, input_path: str, output_path: str, filename: str,
                          user_id: int | None = None, region_id: int | None = None):
    """Xử lý video bằng OpenCV — fallback khi không có ffmpeg.
    VideoWriter được fault-tolerant: nếu codec fail → tiếp tục xử lý detection mà không crash."""
    cap = None
    writer = None
    writer_enabled = True
    frame_idx = 0
    total_frames = 0

    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise Exception("Không thể mở file video đầu vào.")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        file_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0
        duration = total_frames / fps if fps > 0 else 0.0

        print(f"[LPR] {filename} | {width}x{height} {fps:.0f}fps | {duration:.0f}s | {file_size // (1024*1024)}MB | opencv")

        temp_dir = tempfile.gettempdir()
        try:
            disk_usage = shutil.disk_usage(temp_dir)
            free_mb = disk_usage.free // (1024 * 1024)
            if free_mb < 500:
                raise Exception(f"Không đủ dung lượng ổ đĩa: chỉ còn {free_mb}MB trống.")
        except Exception as disk_err:
            if "Không đủ dung lượng" in str(disk_err):
                raise

        with SessionLocal() as db:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "processing"
                job.total_frames = total_frames
                job.fps = fps
                job.duration = duration
                job.file_size = file_size
                db.commit()

        # Ưu tiên mp4v (MP4 chuẩn) → MJPG → XVID
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if writer.isOpened():
            pass  # mp4v OK
        else:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            output_path_avi = os.path.splitext(output_path)[0] + '.avi'
            writer = cv2.VideoWriter(output_path_avi, fourcc, fps, (width, height))
            if writer.isOpened():
                output_path = output_path_avi
            else:
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                output_path_xvid = os.path.splitext(output_path)[0] + '_xvid.avi'
                writer = cv2.VideoWriter(output_path_xvid, fourcc, fps, (width, height))
                if writer.isOpened():
                    output_path = output_path_xvid
                else:
                    writer = None
                    writer_enabled = False
                    print(f"[LPR] ⚠️ Không tạo được VideoWriter — tiếp tục detect không ghi video.")

        font = cv2.FONT_HERSHEY_SIMPLEX
        frame_idx = 0
        processed_count = 0
        written_count = 0
        start_time = time.time()
        first_inference_done = False

        run_inference = init_lpr_service()
        centroid_tracker = CentroidTracker()
        local_snapshot_paths = []

        target_fps = 2
        frame_skip = max(1, int(fps / target_fps))
        stage1_imgsz = 1024

        last_plates = []
        last_plates_frame = -999
        PLATE_DISPLAY_FRAMES = max(1, int(fps * 0.5))

        _BOX_COLORS = [
            (0, 255, 255),    # Vàng (BGR)
            (255, 128, 0),    # Xanh dương đậm
            (0, 255, 0),      # Xanh lá
            (255, 0, 255),    # Tím
            (255, 255, 0),    # Cyan
        ]

        def draw_boxes_on_frame(frame, plates):
            h_frame, w_frame = frame.shape[:2]
            for i, plate in enumerate(plates):
                x1, y1, x2, y2 = plate['bbox']
                if x2 <= x1 or y2 <= y1:
                    continue
                plate_text = plate.get('plate_text') or plate.get('text', '')
                plate_conf = plate.get('plate_confidence') or plate.get('conf', 0)
                label = f"{plate_text} {plate_conf:.2%}" if plate_conf else plate_text

                color = _BOX_COLORS[i % len(_BOX_COLORS)]

                # Viền dày, nổi bật
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

                # Nền chữ + chữ đen
                font_scale = 0.7
                thickness = 2
                (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
                label_y1 = max(0, y1 - th - 10)
                label_y2 = y1
                label_x2 = min(w_frame, x1 + tw + 6)
                cv2.rectangle(frame, (x1, label_y1), (label_x2, label_y2), color, -1)
                cv2.putText(frame, label, (x1 + 3, label_y2 - 4), font, font_scale, (0, 0, 0), thickness)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # ── Kiểm tra tín hiệu dừng ──
            if _cancel_flags.pop(job_id, False):
                print(f"[LPR] Job {job_id} cancelled by user at frame {frame_idx}")
                break

            try:
                if frame is None or frame.size == 0:
                    frame_idx += 1
                    continue

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                if frame_idx % frame_skip != 0:
                    if last_plates and (frame_idx - last_plates_frame) <= PLATE_DISPLAY_FRAMES:
                        draw_boxes_on_frame(frame, last_plates)
                    if writer_enabled:
                        writer, writer_enabled, recovered_path = _safe_write_frame(
                            writer, frame, frame_idx, writer_enabled, output_path, fps, width, height
                        )
                        if recovered_path:
                            output_path = recovered_path
                        if writer_enabled:
                            written_count += 1
                    frame_idx += 1
                    continue

                plates = []
                try:
                    plates = run_inference(
                        pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID, settings.CONF_S3_VID, "video", imgsz=stage1_imgsz
                    )
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    try:
                        plates = run_inference(
                            pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID, settings.CONF_S3_VID, "video", imgsz=stage1_imgsz
                        )
                    except Exception:
                        plates = []
                    torch.cuda.empty_cache()
                except Exception as e:
                    plates = []

                if not first_inference_done:
                    first_inference_done = True

                # Vẽ TẤT CẢ plates từ inference (giữ nguyên behavior cũ)
                # Bao gồm cả "???" và chưa valid — để người dùng thấy box trên video
                if plates:
                    last_plates = plates
                    last_plates_frame = frame_idx

                draw_boxes_on_frame(frame, plates)

                # ── Lưu preview frame (JPEG) cho frontend ──
                try:
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    _preview_frames[job_id] = jpeg.tobytes()
                except Exception:
                    pass

                # Lọc plate hợp lệ CHỈ CHO centroid tracking (không dùng để vẽ)
                valid_plates = []
                for plate in plates:
                    plate_text = plate.get('plate_text') or plate.get('text', '')
                    if not plate_text or plate_text == "???" or "?" in plate_text:
                        continue
                    if not is_valid_plate(plate_text):
                        continue
                    if get_plate_format_score(plate_text) <= 0:
                        continue
                    # Normalize keys cho centroid tracker (expects 'text'/'conf'/'char_confs')
                    valid_plates.append({
                        'text': plate_text,
                        'conf': plate.get('plate_confidence') or plate.get('conf', 0),
                        'bbox': plate['bbox'],
                        'char_confs': plate.get('char_confs'),
                    })

                finalized = centroid_tracker.update(valid_plates, frame_idx=frame_idx, frame_img=pil_img)

                for result in finalized:
                    try:
                        final_text = result['text']
                        final_conf = result['conf']
                        # Ưu tiên first_bbox (frame đầu tiên detect) để ảnh snapshot nhất quán
                        final_bbox = result.get('first_bbox') or result.get('bbox')
                        format_score = result.get('format_score', 0)
                        if not is_valid_plate(final_text) or format_score <= 0:
                            continue
                        first_img = result.get('first_frame_img') or result.get('best_frame_img') or pil_img
                        if final_bbox:
                            annotated_img = draw_plate_results(first_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                        else:
                            annotated_img = draw_plate_results(first_img, [{'bbox': [0, 0, 100, 100], 'text': final_text, 'conf': final_conf}])
                        snapshot_rel_path = save_snapshot_local_only(annotated_img)
                        local_snapshot_paths.append(snapshot_rel_path)
                        with SessionLocal() as db:
                            db_item = Detection(
                                plate_text=final_text, plate_confidence=final_conf,
                                alt_text=result.get('alt_text'), alt_confidence=result.get('alt_confidence'),
                                total_frames=result.get('total_frames', 0),
                                frame_start=result.get('frame_start'), frame_end=result.get('frame_end'),
                                image_path=snapshot_rel_path, source_type="video",
                                video_job_id=job_id, user_id=user_id, region_id=region_id
                            )
                            db.add(db_item)
                            db.commit()
                    except Exception:
                        pass

                if writer_enabled:
                    writer, writer_enabled, recovered_path = _safe_write_frame(
                        writer, frame, frame_idx, writer_enabled, output_path, fps, width, height
                    )
                    if recovered_path:
                        output_path = recovered_path
                    if writer_enabled:
                        written_count += 1

                frame_idx += 1
                processed_count += 1

                if processed_count % 2 == 0 or frame_idx >= total_frames:
                    elapsed = time.time() - start_time
                    raw_fps = frame_idx / elapsed if elapsed > 0 else 0.0
                    pct = int((frame_idx / total_frames) * 100) if total_frames > 0 else 0
                    try:
                        with SessionLocal() as db:
                            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
                            if job:
                                job.progress = pct
                                job.fps = round(raw_fps, 1)
                                job.current_frame = frame_idx
                                db.commit()
                    except Exception:
                        pass

                    if processed_count % 20 == 0 and torch.cuda.is_available():
                        torch.cuda.empty_cache()

            except Exception as frame_err:
                if processed_count < 3:
                    print(f"[ERROR] Frame {frame_idx}: {type(frame_err).__name__}: {frame_err}")
                # Log traceback vào file nếu cần debug
                if processed_count < 1:
                    try:
                        _log_path = os.path.join(tempfile.gettempdir(), 'lpr_frame_errors.log')
                        with open(_log_path, 'a', encoding='utf-8') as _f:
                            _f.write(f"\n=== Frame {frame_idx} | Job {job_id} ===\n")
                            _f.write(f"{traceback.format_exc()}\n")
                    except Exception:
                        pass

                # Luôn ghi frame vào output dù inference fail (không được drop frame)
                if writer and writer_enabled:
                    try:
                        writer.write(frame)
                        written_count += 1
                    except Exception:
                        pass

                frame_idx += 1
                processed_count += 1
                continue

        if cap:
            cap.release()
        if writer and writer_enabled:
            writer.release()
            writer = None

        cleanup_file(input_path)

        merged_results = centroid_tracker.flush_merged()
        for result in merged_results:
            try:
                final_text = result['text']
                final_conf = result['conf']
                # Ưu tiên first_bbox (frame đầu tiên detect) để ảnh snapshot nhất quán
                final_bbox = result.get('first_bbox') or result.get('bbox')
                format_score = result.get('format_score', 0)

                if not is_valid_plate(final_text):
                    continue
                if format_score <= 0:
                    continue

                first_img = result.get('first_frame_img') or result.get('best_frame_img')

                try:
                    if final_bbox and first_img:
                        annotated_img = draw_plate_results(first_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    elif final_bbox and pil_img:
                        annotated_img = draw_plate_results(pil_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    else:
                        from PIL import Image as PILImage
                        annotated_img = PILImage.new('RGB', (640, 480), color=(0, 0, 0))
                except Exception:
                    from PIL import Image as PILImage
                    annotated_img = PILImage.new('RGB', (640, 480), color=(0, 0, 0))

                snapshot_rel_path = save_snapshot_local_only(annotated_img)
                local_snapshot_paths.append(snapshot_rel_path)

                with SessionLocal() as db:
                    db_item = Detection(
                        plate_text=final_text,
                        plate_confidence=final_conf,
                        alt_text=result.get('alt_text'),
                        alt_confidence=result.get('alt_confidence'),
                        total_frames=result.get('total_frames', 0),
                        frame_start=result.get('frame_start'),
                        frame_end=result.get('frame_end'),
                        image_path=snapshot_rel_path,
                        source_type="video",
                        video_job_id=job_id,
                        user_id=user_id,
                        region_id=region_id
                    )
                    db.add(db_item)
                    db.commit()
            except Exception:
                pass

        with SessionLocal() as db:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.progress = 100
                job.current_frame = total_frames
                job.completed_at = get_vietnam_now()
                if writer_enabled or os.path.exists(output_path):
                    job.output_video = output_path
                else:
                    job.output_video = None
                db.commit()

        elapsed = time.time() - start_time
        print(f"[LPR] ✅ Done: {written_count}/{frame_idx} frames | {elapsed:.0f}s | {output_path}")

        # ── Batch upload snapshots lên Cloudinary sau khi xử lý xong ──
        if local_snapshot_paths:
            try:
                cloud_mapping = batch_upload_to_cloudinary(local_snapshot_paths)
                if cloud_mapping:
                    update_detection_paths_to_cloudinary(cloud_mapping)
            except Exception as e:
                print(f"[BATCH-UPLOAD] Loi batch upload: {e}")
            # Xóa các file local còn lại (failed upload hoặc không có Cloudinary)
            for p in local_snapshot_paths:
                cleanup_file(p)

        # ── Dọn dẹp in-memory state ──
        _preview_frames.pop(job_id, None)
        _cancel_flags.pop(job_id, None)

    except Exception as e:
        print(f"[ERROR] Video FAILED at frame {frame_idx}/{total_frames}: {type(e).__name__}: {e}")

        # Dọn dẹp in-memory state
        _preview_frames.pop(job_id, None)
        _cancel_flags.pop(job_id, None)

        if cap:
            try:
                cap.release()
            except Exception:
                pass
        if writer:
            try:
                writer.release()
            except Exception:
                pass
        cleanup_file(input_path)
        cleanup_file(output_path)

        error_detail = f"{type(e).__name__}: {e}"
        if "CUDA" in str(e) or "out of memory" in str(e).lower():
            error_detail = f"GPU hết bộ nhớ (CUDA OOM): {e}"
        elif "No space left" in str(e) or "disk" in str(e).lower():
            error_detail = f"Không đủ dung lượng ổ đĩa: {e}"

        with SessionLocal() as db:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = error_detail
                db.commit()


# =============================================================================
# Entry point — ưu tiên ffmpeg, fallback OpenCV
# =============================================================================

def process_video_background(job_id: int, input_path: str, output_path: str, filename: str,
                             user_id: int | None = None, region_id: int | None = None):
    """Hàm xử lý video chạy ngầm trong luồng riêng biệt.
    Ưu tiên ffmpeg (đáng tin cậy với mọi codec), fallback về OpenCV nếu không có ffmpeg."""
    if _check_ffmpeg():
        _process_video_ffmpeg(job_id, input_path, output_path, filename, user_id, region_id)
    else:
        print("[LPR] ffmpeg không khả dụng, fallback sang OpenCV VideoWriter")
        _process_video_opencv(job_id, input_path, output_path, filename, user_id, region_id)


class PredictService:
    @staticmethod
    async def predict_image(file: UploadFile, user_id: int | None, region_id: int | None, db: Session):
        ext = os.path.splitext(file.filename)[1].lower()
        if not file.content_type.startswith("image/") and ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            raise HTTPException(status_code=400, detail="File tải lên không phải là ảnh hợp lệ.")

        try:
            contents = await file.read()
            nparr = np.frombuffer(contents, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img_bgr is None:
                raise HTTPException(status_code=400, detail="Không thể giải mã file ảnh.")

            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)

            service = init_lpr_service()
            results = service(
                pil_img, settings.CONF_S1_IMG, settings.CONF_S2_IMG, settings.CONF_S3_IMG
            )

            annotated_img = draw_plate_results(pil_img, results)
            snapshot_rel_path = save_snapshot_image(annotated_img)

            if not region_id:
                first_reg = db.query(Region).first()
                if first_reg:
                    region_id = first_reg.id

            for plate in results:
                text = plate.get("plate_text", "")
                conf = plate.get("plate_confidence", 0.0)
                if text and text != "???" and is_valid_plate(text):
                    db_detection = Detection(
                        plate_text=text,
                        plate_confidence=conf,
                        image_path=snapshot_rel_path,
                        source_type="image",
                        user_id=user_id,
                        region_id=region_id
                    )
                    db.add(db_detection)
            db.commit()

            # Transform keys to match frontend expectations (text/conf)
            frontend_results = []
            for r in results:
                frontend_results.append({
                    "text": r.get("plate_text", ""),
                    "conf": r.get("plate_confidence", 0.0),
                    "bbox": r.get("bbox", []),
                    "alt_text": r.get("alt_text"),
                    "alt_confidence": r.get("alt_confidence"),
                    "char_confs": r.get("char_confs", []),
                })

            return {
                "status": "success",
                "results": frontend_results,
                "annotated_image": snapshot_rel_path
            }
        except HTTPException as he:
            raise he
        except Exception as e:
            return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    @staticmethod
    async def predict_video(file: UploadFile, user_id: int | None, region_id: int | None, db: Session):
        ext = os.path.splitext(file.filename)[1].lower()
        if not file.content_type.startswith("video/") and ext not in ['.mp4', '.avi', '.mov', '.mkv']:
            raise HTTPException(status_code=400, detail="File tải lên không phải là video hợp lệ.")

        temp_dir = tempfile.gettempdir()
        task_uuid = str(uuid.uuid4())

        input_path = os.path.join(temp_dir, f"{task_uuid}_in{ext}")
        output_path = os.path.join(temp_dir, f"{task_uuid}_out.mp4")

        try:
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0

            if not region_id:
                first_reg = db.query(Region).first()
                if first_reg:
                    region_id = first_reg.id

            db_job = VideoJob(
                user_id=user_id,
                filename=file.filename,
                file_path=input_path,
                file_size=file_size,
                status="pending",
                progress=0,
                created_at=get_vietnam_now()
            )
            db.add(db_job)
            db.commit()
            db.refresh(db_job)

            job_id = db_job.id

            thread = threading.Thread(
                target=process_video_background,
                args=(job_id, input_path, output_path, file.filename, user_id, region_id)
            )
            thread.daemon = True
            thread.start()

            log_activity(db, user_id, "Tải lên video", f"Khởi chạy tiến trình xử lý video '{file.filename}' (Job #{job_id}).")

            return {
                "status": "success",
                "task_id": str(job_id),
                "message": "Bắt đầu xử lý video."
            }
        except Exception as e:
            cleanup_file(input_path)
            cleanup_file(output_path)
            return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    @staticmethod
    async def get_task_status(task_id: str, db: Session):
        try:
            job_id = int(task_id)
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                return {
                    "task_id": str(job.id),
                    "status": job.status,
                    "progress": job.progress or 0,
                    "fps": job.fps or 0.0,
                    "current_frame": job.current_frame or 0,
                    "total_frames": job.total_frames or 0,
                    "error": job.error_message
                }
        except ValueError:
            pass

        if task_id not in tasks_db:
            raise HTTPException(status_code=404, detail="Không tìm thấy task ID.")
        task_info = tasks_db[task_id]
        return {
            "task_id": task_id,
            "status": task_info["status"],
            "progress": task_info["progress"],
            "fps": task_info["fps"],
            "current_frame": task_info["current_frame"],
            "total_frames": task_info["total_frames"],
            "error": task_info["error"]
        }

    @staticmethod
    async def download_task_result(task_id: str, background_tasks: BackgroundTasks, db: Session):
        try:
            job_id = int(task_id)
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                if job.status == "processing":
                    raise HTTPException(status_code=400, detail="Video đang xử lý.")
                elif job.status == "failed":
                    raise HTTPException(status_code=400, detail=f"Xử lý video thất bại: {job.error_message}")

                output_path = job.output_video
                if not output_path or not os.path.exists(output_path):
                    raise HTTPException(status_code=404, detail="File video kết quả không tồn tại.")

                # Xác định media type dựa trên extension thực tế
                ext = os.path.splitext(output_path)[1].lower()
                media_type_map = {
                    '.mp4': 'video/mp4',
                    '.avi': 'video/x-msvideo',
                    '.mkv': 'video/x-matroska',
                }
                media_type = media_type_map.get(ext, 'video/mp4')

                # Giữ nguyên tên gốc, thêm tiền tố "processed_"
                base_name = os.path.splitext(job.filename)[0]
                download_name = f"processed_{base_name}{ext}"

                response = FileResponse(
                    output_path,
                    media_type=media_type,
                    filename=download_name
                )

                background_tasks.add_task(cleanup_file, output_path)
                return response
        except ValueError:
            pass

        if task_id not in tasks_db:
            raise HTTPException(status_code=404, detail="Không tìm thấy task ID.")

        task_info = tasks_db[task_id]
        if task_info["status"] == "processing":
            raise HTTPException(status_code=400, detail="Video đang xử lý.")
        elif task_info["status"] == "failed":
            raise HTTPException(status_code=400, detail=f"Xử lý video thất bại: {task_info['error']}")

        output_path = task_info["output_file"]
        if not os.path.exists(output_path):
            raise HTTPException(status_code=404, detail="File không tồn tại.")

        response = FileResponse(
            output_path,
            media_type="video/mp4",
            filename=f"processed_{task_info['filename']}"
        )

        background_tasks.add_task(cleanup_file, output_path)
        background_tasks.add_task(lambda: tasks_db.pop(task_id, None))
        return response

    @staticmethod
    async def handle_websocket(websocket: WebSocket):
        """WebSocket xử lý nhận diện biển số thời gian thực từ webcam.
        Sử dụng CentroidTracker để theo dõi và chống trùng lặp qua các frame."""
        await websocket.accept()
        centroid_tracker = CentroidTracker()
        ws_frame_idx = 0
        local_snapshot_paths = []

        try:
            while True:
                data = await websocket.receive_json()
                image_data = data.get("image")
                if not image_data:
                    await websocket.send_json({"status": "error", "message": "Thiếu dữ liệu ảnh."})
                    continue

                conf1 = float(data.get("conf1", settings.CONF_S1_IMG))
                conf2 = float(data.get("conf2", settings.CONF_S2_IMG))
                conf3 = float(data.get("conf3", settings.CONF_S3_IMG))

                try:
                    user_id = int(data.get("user_id")) if data.get("user_id") is not None else None
                except (ValueError, TypeError):
                    user_id = None

                try:
                    region_id = int(data.get("region_id")) if data.get("region_id") is not None else None
                except (ValueError, TypeError):
                    region_id = None

                try:
                    camera_id = int(data.get("camera_id")) if data.get("camera_id") is not None else None
                except (ValueError, TypeError):
                    camera_id = None

                if "," in image_data:
                    image_data = image_data.split(",")[1]

                img_bytes = base64.b64decode(image_data)
                nparr = np.frombuffer(img_bytes, np.uint8)
                img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img_bgr is None:
                    await websocket.send_json({"status": "error", "message": "Không thể giải mã ảnh."})
                    continue

                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)

                service = init_lpr_service()
                results = await asyncio.to_thread(
                    service, pil_img, conf1, conf2, conf3, "video", 640
                )

                valid_plates = []
                for plate in results:
                    # Pipeline trả về plate_text/plate_confidence,
                    # tracker expects text/conf — normalize cả 2 format
                    text = plate.get("plate_text") or plate.get("text", "")
                    if not text or text == "???" or "?" in text:
                        continue
                    if not is_valid_plate(text):
                        continue
                    if get_plate_format_score(text) <= 0:
                        continue
                    valid_plates.append({
                        "text": text,
                        "conf": plate.get("plate_confidence") or plate.get("conf", 0),
                        "bbox": plate.get("bbox"),
                        "char_confs": plate.get("char_confs"),
                    })

                finalized = centroid_tracker.update(valid_plates, frame_idx=ws_frame_idx, frame_img=pil_img)
                ws_frame_idx += 1

                for result in finalized:
                    final_text = result['text']
                    final_conf = result['conf']
                    # Ưu tiên first_bbox (frame đầu tiên detect) để ảnh snapshot nhất quán
                    final_bbox = result.get('first_bbox') or result.get('bbox')
                    format_score = result.get('format_score', 0)

                    if not is_valid_plate(final_text):
                        continue
                    if format_score <= 0:
                        continue

                    first_img = result.get('first_frame_img') or result.get('best_frame_img') or pil_img

                    if final_bbox:
                        annotated_img = draw_plate_results(first_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    else:
                        annotated_img = draw_plate_results(first_img, [{'bbox': [0, 0, 100, 100], 'text': final_text, 'conf': final_conf}])
                    snapshot_rel_path = save_snapshot_local_only(annotated_img)
                    local_snapshot_paths.append(snapshot_rel_path)

                    with SessionLocal() as db:
                        actual_region_id = region_id
                        if not actual_region_id:
                            first_reg = db.query(Region).first()
                            if first_reg:
                                actual_region_id = first_reg.id

                        db_item = Detection(
                            plate_text=final_text,
                            plate_confidence=final_conf,
                            alt_text=result.get('alt_text'),
                            alt_confidence=result.get('alt_confidence'),
                            total_frames=result.get('total_frames', 0),
                            frame_start=result.get('frame_start'),
                            frame_end=result.get('frame_end'),
                            image_path=snapshot_rel_path,
                            source_type="camera",
                            user_id=user_id,
                            region_id=actual_region_id,
                            camera_id=camera_id
                        )
                        db.add(db_item)
                        db.commit()

                active_plates = centroid_tracker.get_active_plates()
                clean_finalized = [{k: v for k, v in r.items() if k not in ('best_frame_img', 'first_frame_img')} for r in finalized]
                await websocket.send_json({
                    "status": "success",
                    "results": clean_finalized,
                    "active_plates": active_plates
                })

        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await websocket.send_json({"status": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            # ── Batch upload snapshots lên Cloudinary khi ngắt kết nối ──
            if local_snapshot_paths:
                try:
                    cloud_mapping = batch_upload_to_cloudinary(local_snapshot_paths)
                    if cloud_mapping:
                        update_detection_paths_to_cloudinary(cloud_mapping)
                except Exception as e:
                    print(f"[BATCH-UPLOAD] Loi batch upload: {e}")
                # Xóa các file local còn lại (failed upload hoặc không có Cloudinary)
                for p in local_snapshot_paths:
                    cleanup_file(p)

    # =========================================================================
    # Video Preview + Cancel
    # =========================================================================

    @staticmethod
    async def get_preview_frame(task_id: str):
        """Trả về frame preview mới nhất (JPEG) khi video đang xử lý."""
        from fastapi.responses import StreamingResponse
        from fastapi import HTTPException

        try:
            job_id = int(task_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid task ID")

        frame_bytes = _preview_frames.get(job_id)
        if not frame_bytes:
            raise HTTPException(status_code=404, detail="No preview available yet")
        return StreamingResponse(iter([frame_bytes]), media_type="image/jpeg")

    @staticmethod
    async def cancel_task(task_id: str, db: Session):
        """Gửi tín hiệu dừng xử lý video. Ảnh đã xử lý vẫn được lưu."""
        from fastapi import HTTPException

        try:
            job_id = int(task_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid task ID")

        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Task not found")
        if job.status != "processing":
            raise HTTPException(status_code=400, detail="Task is not currently processing")

        _cancel_flags[job_id] = True
        print(f"[LPR] Cancel signal sent for job {job_id}")
        return {"status": "success", "message": "Đã gửi tín hiệu dừng xử lý"}
