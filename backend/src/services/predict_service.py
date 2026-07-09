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

def process_video_background(job_id: int, input_path: str, output_path: str, filename: str, user_id: int | None = None, region_id: int | None = None):
    """Hàm xử lý video chạy ngầm trong luồng riêng biệt, cập nhật trực tiếp vào DB."""
    cap = None
    writer = None
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

        # Kiểm tra dung lượng ổ đĩa còn đủ không (dự phòng ~3x kích thước input)
        required_space = file_size * 3  # Dự phòng 3x dung lượng input
        temp_dir = tempfile.gettempdir()
        try:
            disk_usage = shutil.disk_usage(temp_dir)
            free_space = disk_usage.free
            if required_space > free_space and free_space < 500 * 1024 * 1024:  # < 500MB free
                raise Exception(f"Không đủ dung lượng ổ đĩa: cần ~{required_space // (1024*1024)}MB, chỉ còn {free_space // (1024*1024)}MB trống.")
        except Exception as disk_err:
            if "Không đủ dung lượng" in str(disk_err):
                raise
            # Nếu không kiểm tra được disk thì bỏ qua

        # Kiểm tra GPU memory trước khi bắt đầu
        if torch.cuda.is_available():
            gpu_mem_free = torch.cuda.mem_get_info(0)[0] / 1024**2  # MB free
            print(f"[LPR] GPU memory free: {gpu_mem_free:.0f} MB")
            if gpu_mem_free < 500:  # < 500MB free GPU
                print(f"[LPR] ⚠️  GPU memory thấp ({gpu_mem_free:.0f}MB free), có thể gặp OOM")

        # Cập nhật thông tin ban đầu của video vào database
        with SessionLocal() as db:
            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
            if job:
                job.status = "processing"
                job.total_frames = total_frames
                job.fps = fps
                job.duration = duration
                job.file_size = file_size
                db.commit()

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            if not writer.isOpened():
                raise Exception("Không khởi tạo được VideoWriter.")

        font = cv2.FONT_HERSHEY_SIMPLEX
        frame_idx = 0
        processed_count = 0
        start_time = time.time()
        first_inference_done = False

        service = init_lpr_service()
        centroid_tracker = CentroidTracker()

        # Frame skip: xử lý ~2 frames/giây video
        # Với video 30fps → xử lý mỗi 15 frame → ~1508 frames cần inference cho video 11309 frames
        target_fps = 2
        frame_skip = max(1, int(fps / target_fps))

        # Giảm độ phân giải Stage 1 cho video (1024 thay vì 1280)
        stage1_imgsz = 1024

        # Hiển thị box: giữ kết quả detection trong0.5s (15 frames ở30fps)
        # last_plates: list plates gần nhất, last_plates_frame: frame_idx khi detect
        last_plates = []
        last_plates_frame = -999
        PLATE_DISPLAY_FRAMES = max(1, int(fps * 0.5))  # ~15 frames ở30fps

        def draw_boxes_on_frame(frame, plates):
            """Vẽ bbox + text lên frame."""
            for plate in plates:
                x1, y1, x2, y2 = plate['bbox']
                plate_text = plate['text']
                plate_conf = plate.get('conf', 0)
                label = f"{plate_text} {plate_conf:.0%}" if plate_conf else plate_text
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), font, 0.8, (0, 255, 0), 2)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)

            # Skip frame: vẫn vẽ box gần nhất nếu trong khoảng0.5s
            if frame_idx % frame_skip != 0:
                if last_plates and (frame_idx - last_plates_frame) <= PLATE_DISPLAY_FRAMES:
                    draw_boxes_on_frame(frame, last_plates)
                writer.write(frame)
                frame_idx += 1
                continue

            # --- Đã đến frame cần xử lý inference ---
            try:
                plates = service.run_inference(
                    pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID, settings.CONF_S3_VID, stage1_imgsz
                )
            except torch.cuda.OutOfMemoryError:
                print(f"[WARN] CUDA OOM at frame {frame_idx}, clearing cache and retrying with smaller imgsz...")
                torch.cuda.empty_cache()
                try:
                    plates = service.run_inference(
                        pil_img, settings.CONF_S1_VID, settings.CONF_S2_VID, settings.CONF_S3_VID, 640
                    )
                except Exception as e2:
                    print(f"[WARN] Inference failed again at frame {frame_idx}: {e2}")
                    plates = []
                torch.cuda.empty_cache()
            except Exception as e:
                print(f"[WARN] Inference error at frame {frame_idx}: {type(e).__name__}: {e}")
                plates = []

            if not first_inference_done:
                first_inference_done = True

            # Cập nhật last_plates nếu có detection mới
            if plates:
                last_plates = plates
                last_plates_frame = frame_idx

            # Vẽ bbox lên frame output
            draw_boxes_on_frame(frame, plates)

            # Centroid Tracking + Character Voting
            # Lọc bỏ detection không hợp lệ trước khi tracking
            # Chỉ giữ biển có format đúng: 8-10 ký tự, XXLetterXX
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

            # Lưu các track đã finalize (biển số đã ổn định) vào DB
            for result in finalized:
                try:
                    final_text = result['text']
                    final_conf = result['conf']
                    final_bbox = result.get('bbox')
                    format_score = result.get('format_score', 0)

                    # Kiểm tra format biển số VN + format score
                    if not is_valid_plate(final_text):
                        continue
                    if format_score <= 0:
                        continue

                    # Vẽ snapshot với bounding box thật (nếu có)
                    if final_bbox:
                        annotated_img = draw_plate_results(pil_img, [{'bbox': final_bbox, 'text': final_text, 'conf': final_conf}])
                    else:
                        annotated_img = draw_plate_results(pil_img, [{'bbox': [0, 0, 100, 100], 'text': final_text, 'conf': final_conf}])
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
                    print(f"[WARN] Save detection error: {e}")

            try:
                writer.write(frame)
            except Exception as e:
                print(f"[WARN] VideoWriter write error at frame {frame_idx}: {e}")
                # Thử tạo lại VideoWriter với codec XVID
                try:
                    writer.release()
                    fourcc_fallback = cv2.VideoWriter_fourcc(*'XVID')
                    writer = cv2.VideoWriter(output_path, fourcc_fallback, fps, (width, height))
                    if writer.isOpened():
                        writer.write(frame)
                        print(f"[INFO] VideoWriter recovered with XVID codec")
                    else:
                        print(f"[ERROR] VideoWriter recovery failed")
                except Exception as e2:
                    print(f"[ERROR] VideoWriter recovery failed: {e2}")

            frame_idx += 1
            processed_count += 1

            # Cập nhật progress mỗi2 processed frames
            if processed_count % 2 == 0 or frame_idx >= total_frames:
                elapsed = time.time() - start_time
                # Tốc độ: raw frames đọc được / giây (đồng bộ với current_frame)
                raw_fps = frame_idx / elapsed if elapsed > 0 else 0.0
                pct = int((frame_idx / total_frames) * 100) if total_frames > 0 else 0

                # ETA = số raw frames còn lại / tốc độ raw fps
                remaining = total_frames - frame_idx
                eta_seconds = int(remaining / raw_fps) if raw_fps > 0 else 0

                try:
                    with SessionLocal() as db:
                        job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
                        if job:
                            job.progress = pct
                            job.fps = round(raw_fps, 1)
                            job.current_frame = frame_idx
                            db.commit()
                except Exception as e:
                    print(f"[WARN] Progress update DB error: {e}")

                # Giải phóng GPU memory định kỳ (mỗi20 processed frames)
                # Tránh tích lũy tensor → OOM trên GPU có VRAM thấp (6GB RTX 3050)
                if processed_count % 20 == 0 and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    gpu_mem_free = torch.cuda.mem_get_info(0)[0] / 1024**2
                    if gpu_mem_free < 300:
                        print(f"[WARN] GPU memory critically low: {gpu_mem_free:.0f}MB free at frame {frame_idx}")

        cap.release()
        writer.release()
        cleanup_file(input_path)

        # Flush tất cả kết quả đã merge còn lại trong buffer
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

                # Vẽ snapshot — dùng ảnh trắng nếu pil_img không khả dụng
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

        with SessionLocal() as db:
            job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.progress = 100
                job.current_frame = total_frames
                job.completed_at = get_vietnam_now()
                job.output_video = output_path
                db.commit()

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] Video processing failed at frame {frame_idx if 'frame_idx' in dir() else '?'}/{total_frames if 'total_frames' in dir() else '?'}: {e}")
        print(f"[ERROR] Full traceback:\n{tb}")

        if cap:
            cap.release()
        if writer:
            writer.release()
        cleanup_file(input_path)
        cleanup_file(output_path)

        # Hiển thị lỗi chi tiết hơn cho frontend
        error_detail = str(e)
        if "CUDA" in error_detail or "out of memory" in error_detail.lower():
            error_detail = f"GPU hết bộ nhớ (CUDA OOM): {e}. Thử giảm độ phân giải video hoặc dùng CPU."
        elif "No space left" in error_detail or "disk" in error_detail.lower():
            error_detail = f"Không đủ dung lượng ổ đĩa: {e}"
        elif "mp4v" in error_detail or "VideoWriter" in error_detail:
            error_detail = f"Lỗi codec video output: {e}"

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
