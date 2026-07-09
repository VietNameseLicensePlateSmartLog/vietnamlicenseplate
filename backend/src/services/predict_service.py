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
import torch
from datetime import datetime
from PIL import Image
from fastapi import UploadFile, BackgroundTasks, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.config.database import SessionLocal
from src.models import models, schemas
from src.services.ai_pipeline import init_lpr_service, draw_plate_results
from src.services.tracking import CentroidTracker
from src.services.validation import is_valid_plate, get_plate_format_score
from src.utils.helpers import save_snapshot_image, cleanup_file, log_activity, get_vietnam_now

# Lưu trữ trạng thái video task cũ dùng UUID
tasks_db = {}

def _safe_write_frame(writer, frame, frame_idx, writer_enabled, output_path, fps, width, height):
    """Ghi frame vào output video một cách an toàn.
    Trả về (writer, writer_enabled): writer có thể thay đổi nếu recovery."""
    if not writer_enabled or writer is None:
        return writer, writer_enabled

    try:
        ret = writer.write(frame)
        # OpenCV VideoWriter.write() trả về None hoặc bool
        # Không thể kiểm tra return value đáng tin → catch exception
        return writer, writer_enabled
    except Exception as e:
        print(f"[WARN] VideoWriter.write() failed at frame {frame_idx}: {type(e).__name__}: {e}")

        # Thử recovery 1 lần: release → tạo lại với XVID
        try:
            if writer:
                writer.release()
        except Exception:
            pass

        try:
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            new_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            if new_writer.isOpened():
                try:
                    new_writer.write(frame)
                    print(f"[INFO] VideoWriter recovered with XVID at frame {frame_idx}")
                    return new_writer, True
                except Exception as e2:
                    print(f"[WARN] XVID recovery write also failed: {e2}")
                    new_writer.release()
            else:
                print("[WARN] XVID VideoWriter also failed to open")
        except Exception as e2:
            print(f"[WARN] XVID recovery error: {e2}")

        # Recovery thất bại → tắt writer, tiếp tục processing mà không ghi video
        print(f"[WARN] ⚠️ VideoWriter disabled at frame {frame_idx}. "
              "Processing continues — detections are still saved to database.")
        return None, False


def process_video_background(job_id: int, input_path: str, output_path: str, filename: str, user_id: int | None = None, region_id: int | None = None):
    """Hàm xử lý video chạy ngầm trong luồng riêng biệt, cập nhật trực tiếp vào DB.
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

        print(f"[LPR] Video: {filename} | {width}x{height} | {fps:.1f}fps | "
              f"{total_frames} frames | {duration:.1f}s | {file_size // (1024*1024)}MB")

        # Kiểm tra dung lượng ổ đĩa
        temp_dir = tempfile.gettempdir()
        try:
            disk_usage = shutil.disk_usage(temp_dir)
            free_mb = disk_usage.free // (1024 * 1024)
            print(f"[LPR] Disk free: {free_mb}MB on {temp_dir}")
            if free_mb < 500:
                raise Exception(f"Không đủ dung lượng ổ đĩa: chỉ còn {free_mb}MB trống trên {temp_dir}.")
        except Exception as disk_err:
            if "Không đủ dung lượng" in str(disk_err):
                raise
            # Nếu không kiểm tra được disk thì bỏ qua

        # Kiểm tra GPU memory
        if torch.cuda.is_available():
            gpu_mem_free = torch.cuda.mem_get_info(0)[0] / 1024**2
            print(f"[LPR] GPU memory free: {gpu_mem_free:.0f} MB")
            if gpu_mem_free < 500:
                print(f"[LPR] ⚠️  GPU memory thấp ({gpu_mem_free:.0f}MB free), có thể gặp OOM")

        # Cập nhật DB
        with SessionLocal() as db:
            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
            if job:
                job.status = "processing"
                job.total_frames = total_frames
                job.fps = fps
                job.duration = duration
                job.file_size = file_size
                db.commit()

        # Tạo VideoWriter — thử mp4v trước, fallback XVID
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            print(f"[WARN] mp4v codec failed, trying XVID...")
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            # Đổi phần mở rộng output sang .avi cho XVID
            output_path_avi = os.path.splitext(output_path)[0] + '.avi'
            writer = cv2.VideoWriter(output_path_avi, fourcc, fps, (width, height))
            if writer.isOpened():
                output_path = output_path_avi  # Dùng path mới
                print(f"[INFO] Using XVID codec → {output_path}")
            else:
                writer = None
                writer_enabled = False
                print(f"[WARN] ⚠️ Không tạo được VideoWriter (mp4v + XVID đều fail). "
                      "Tiếp tục xử lý detection mà không ghi video output.")
        else:
            print(f"[INFO] Using mp4v codec → {output_path}")

        font = cv2.FONT_HERSHEY_SIMPLEX
        frame_idx = 0
        processed_count = 0
        start_time = time.time()
        first_inference_done = False
        write_fail_count = 0
        MAX_WRITE_FAILS = 5  # Tắt writer sau 5 lần fail liên tiếp

        service = init_lpr_service()
        centroid_tracker = CentroidTracker()

        # Frame skip: xử lý ~2 frames/giây video
        target_fps = 2
        frame_skip = max(1, int(fps / target_fps))

        # Giảm độ phân giải Stage 1 cho video (1024 thay vì 1280)
        stage1_imgsz = 1024

        # Hiển thị box: giữ kết quả detection trong 0.5s
        last_plates = []
        last_plates_frame = -999
        PLATE_DISPLAY_FRAMES = max(1, int(fps * 0.5))

        def draw_boxes_on_frame(frame, plates):
            """Vẽ bbox + text lên frame."""
            for plate in plates:
                x1, y1, x2, y2 = plate['bbox']
                plate_text = plate['text']
                plate_conf = plate.get('conf', 0)
                # Hiển thị confidence với 2 chữ số thập phân (VD: 99.70%)
                label = f"{plate_text} {plate_conf:.2%}" if plate_conf else plate_text
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), font, 0.8, (0, 255, 0), 2)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            try:
                # Validate frame
                if frame is None or frame.size == 0:
                    frame_idx += 1
                    continue

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                # Skip frame: vẫn vẽ box gần nhất nếu trong khoảng 0.5s
                if frame_idx % frame_skip != 0:
                    if last_plates and (frame_idx - last_plates_frame) <= PLATE_DISPLAY_FRAMES:
                        draw_boxes_on_frame(frame, last_plates)
                    if writer_enabled:
                        writer, writer_enabled = _safe_write_frame(
                            writer, frame, frame_idx, writer_enabled, output_path, fps, width, height
                        )
                    frame_idx += 1
                    continue

                # --- Frame cần inference ---
                plates = []
                try:
                    plates = service.run_inference(
                        pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID, settings.CONF_S3_VID, stage1_imgsz
                    )
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    try:
                        plates = service.run_inference(
                            pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID, settings.CONF_S3_VID, 640
                        )
                    except Exception:
                        plates = []
                    torch.cuda.empty_cache()
                except Exception as e:
                    plates = []

                if not first_inference_done:
                    first_inference_done = True

                if plates:
                    last_plates = plates
                    last_plates_frame = frame_idx

                draw_boxes_on_frame(frame, plates)

                # Centroid Tracking
                valid_plates = []
                for plate in plates:
                    plate_text = plate['text']
                    if not plate_text or plate_text == "???" or "?" in plate_text:
                        continue
                    if not is_valid_plate(plate_text):
                        continue
                    if get_plate_format_score(plate_text) <= 0:
                        continue
                    valid_plates.append(plate)

                finalized = centroid_tracker.update(valid_plates, frame_idx=frame_idx)

                # Lưu finalized detections vào DB
                for result in finalized:
                    try:
                        final_text = result['text']
                        final_conf = result['conf']
                        final_bbox = result.get('bbox')
                        format_score = result.get('format_score', 0)
                        if not is_valid_plate(final_text) or format_score <= 0:
                            continue
                        if final_bbox:
                            annotated_img = draw_plate_results(pil_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                        else:
                            annotated_img = draw_plate_results(pil_img, [{'bbox': [0, 0, 100, 100], 'text': final_text, 'conf': final_conf}])
                        snapshot_rel_path = save_snapshot_image(annotated_img)
                        with SessionLocal() as db:
                            db_item = models.Detection(
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

                # Ghi frame output
                if writer_enabled:
                    writer, writer_enabled = _safe_write_frame(
                        writer, frame, frame_idx, writer_enabled, output_path, fps, width, height
                    )

                frame_idx += 1
                processed_count += 1

                # Progress update
                if processed_count % 2 == 0 or frame_idx >= total_frames:
                    elapsed = time.time() - start_time
                    raw_fps = frame_idx / elapsed if elapsed > 0 else 0.0
                    pct = int((frame_idx / total_frames) * 100) if total_frames > 0 else 0
                    try:
                        with SessionLocal() as db:
                            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
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
                # BẤT KỲ lỗi nào trong loop body → log + skip frame, KHÔNG crash
                _frame_err_tb = traceback.format_exc()
                print(f"[ERROR] Frame {frame_idx} error: {type(frame_err).__name__}: {frame_err}")
                print(f"[ERROR] Frame {frame_idx} traceback:\n{_frame_err_tb}")

                # Ghi traceback ra file để debug
                try:
                    _log_path = os.path.join(tempfile.gettempdir(), 'lpr_frame_errors.log')
                    with open(_log_path, 'a', encoding='utf-8') as _f:
                        _f.write(f"\n=== Frame {frame_idx} | Job {job_id} ===\n")
                        _f.write(f"{type(frame_err).__name__}: {frame_err}\n")
                        _f.write(_frame_err_tb)
                        _f.write("\n")
                    print(f"[ERROR] Traceback logged to: {_log_path}")
                except Exception:
                    pass

                # Skip frame lỗi, tiếp tục frame tiếp theo
                frame_idx += 1
                continue

        # --- Xử lý sau khi đọc hết video ---
        if cap:
            cap.release()
        if writer and writer_enabled:
            writer.release()
            writer = None

        cleanup_file(input_path)

        # Flush tất cả kết quả merge còn lại trong buffer
        merged_results = centroid_tracker.flush_merged()
        for result in merged_results:
            try:
                final_text = result['text']
                final_conf = result['conf']
                final_bbox = result.get('bbox')
                format_score = result.get('format_score', 0)

                if not is_valid_plate(final_text):
                    continue
                if format_score <= 0:
                    continue

                try:
                    if final_bbox and pil_img:
                        annotated_img = draw_plate_results(pil_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    else:
                        from PIL import Image as PILImage
                        annotated_img = PILImage.new('RGB', (640, 480), color=(0, 0, 0))
                except Exception:
                    from PIL import Image as PILImage
                    annotated_img = PILImage.new('RGB', (640, 480), color=(0, 0, 0))

                snapshot_rel_path = save_snapshot_image(annotated_img)

                with SessionLocal() as db:
                    db_item = models.Detection(
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
            except Exception as e:
                print(f"[WARN] Flush merged error: {e}")

        # Hoàn thành — output_path có thể None nếu writer bị tắt
        with SessionLocal() as db:
            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
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

        print(f"[LPR] ✅ Video processing completed: {frame_idx} frames, "
              f"writer={'ON' if writer_enabled else 'OFF (detections only)'}")

    except Exception as e:
        tb = traceback.format_exc()
        _fi = frame_idx if 'frame_idx' in dir() else '?'
        _tf = total_frames if 'total_frames' in dir() and total_frames else '?'
        print(f"[ERROR] Video processing FAILED at frame {_fi}/{_tf}: {type(e).__name__}: {e}")
        print(f"[ERROR] Full traceback:\n{tb}")

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
            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = error_detail
                db.commit()


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
            results = service.run_inference(
                pil_img, settings.CONF_S1_IMG, settings.CONF_S2_IMG, settings.CONF_S3_IMG
            )
            
            # Vẽ kết quả vẽ bounding box làm snapshot
            annotated_img = draw_plate_results(pil_img, results)
            snapshot_rel_path = save_snapshot_image(annotated_img)
            
            # Nếu không có region_id, thử lấy phân vùng mặc định đầu tiên
            if not region_id:
                first_reg = db.query(models.Region).first()
                if first_reg:
                    region_id = first_reg.id

            # Lưu kết quả nhận diện của ảnh vào Database (conf: 0-1)
            for plate in results:
                text = plate["text"]
                conf = plate["conf"]
                if text and text != "???":
                    db_detection = models.Detection(
                        plate_text=text,
                        plate_confidence=conf,  # 0-1 trong DB
                        image_path=snapshot_rel_path,
                        source_type="image",
                        user_id=user_id,
                        region_id=region_id
                    )
                    db.add(db_detection)
            db.commit()

            return {
                "status": "success",
                "results": results,  # conf: 0-1, frontend × 100 khi display
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

            # Nếu không có region_id, thử lấy phân vùng mặc định đầu tiên
            if not region_id:
                first_reg = db.query(models.Region).first()
                if first_reg:
                    region_id = first_reg.id

            # Tạo bản ghi Job Video vào database
            db_job = models.VideoJob(
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
            
            # Chạy luồng nền để xử lý video
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
        # Thử tìm kiếm trong database trước
        try:
            job_id = int(task_id)
            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
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

        # Phục hồi tìm trong tasks_db trong bộ nhớ (dành cho các task cũ dùng UUID)
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
        # Thử tìm kiếm trong database trước
        try:
            job_id = int(task_id)
            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
            if job:
                if job.status == "processing":
                    raise HTTPException(status_code=400, detail="Video đang xử lý.")
                elif job.status == "failed":
                    raise HTTPException(status_code=400, detail=f"Xử lý video thất bại: {job.error_message}")
                    
                output_path = job.output_video
                if not output_path or not os.path.exists(output_path):
                    raise HTTPException(status_code=404, detail="File video kết quả không tồn tại.")
                    
                response = FileResponse(
                    output_path, 
                    media_type="video/mp4", 
                    filename=f"processed_{job.filename}"
                )
                
                # Đăng ký tác vụ dọn dẹp file sau khi tải
                background_tasks.add_task(cleanup_file, output_path)
                return response
        except ValueError:
            pass

        # Phục hồi từ tasks_db cũ dùng UUID
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
                    service.run_inference, pil_img, conf1, conf2, conf3, 640
                )

                # Lọc bỏ detection không hợp lệ trước khi tracking
                # Chỉ giữ biển có format đúng: 8-10 ký tự, XXLetterXX
                valid_plates = []
                for plate in results:
                    text = plate["text"]
                    if not text or text == "???" or "?" in text:
                        continue
                    if not is_valid_plate(text):
                        continue
                    if get_plate_format_score(text) <= 0:
                        continue
                    valid_plates.append(plate)

                # Centroid Tracking + Character Voting
                finalized = centroid_tracker.update(valid_plates, frame_idx=centroid_tracker._frame_idx)

                # Lưu các track đã finalize (biển số đã ổn định) vào DB
                for result in finalized:
                    final_text = result['text']
                    final_conf = result['conf']
                    final_bbox = result.get('bbox')
                    format_score = result.get('format_score', 0)

                    if not is_valid_plate(final_text):
                        continue
                    if format_score <= 0:
                        continue

                    # Vẽ snapshot với bounding box thật
                    if final_bbox:
                        annotated_img = draw_plate_results(pil_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    else:
                        annotated_img = draw_plate_results(pil_img, [{'bbox': [0, 0, 100, 100], 'text': final_text, 'conf': final_conf}])
                    snapshot_rel_path = save_snapshot_image(annotated_img)

                    with SessionLocal() as db:
                        actual_region_id = region_id
                        if not actual_region_id:
                            first_reg = db.query(models.Region).first()
                            if first_reg:
                                actual_region_id = first_reg.id

                        db_item = models.Detection(
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
                            region_id=actual_region_id
                        )
                        db.add(db_item)
                        db.commit()

                # Gửi kết quả về client:
                # - finalized: biển đã ổn định (lưu DB, hiển thị history)
                # - active_plates: các biển đang track (hiển thị live bbox)
                # Conf values: 0-1 (frontend × 100 khi display)
                active_plates = centroid_tracker.get_active_plates()
                await websocket.send_json({
                    "status": "success",
                    "results": finalized,
                    "active_plates": active_plates
                })

        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await websocket.send_json({"status": "error", "message": str(e)})
            except Exception:
                pass
