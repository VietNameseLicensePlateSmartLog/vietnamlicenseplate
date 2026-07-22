"""Camera Connection Manager — quản lý kết nối RTSP/IP camera từ database.

Tạo một singleton CameraConnectionManager để quản lý tất cả kết nối camera
đang hoạt động. Mỗi camera được kết nối qua cv2.VideoCapture với auto-reconnect.

Flow:
  1. Frontend gọi connect(camera_id) → Manager đọc URL từ DB → mở cv2.VideoCapture
  2. CameraConnection chạy read loop: read frame → detect → lưu DB
  3. Nếu mất kết nối → auto-reconnect theo config trong DB (reconnect_interval, max_attempts)
  4. Broadcast kết quả qua WebSocket clients đang kết nối
"""
import asyncio
import logging
import time
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from typing import Optional

from sqlalchemy.orm import Session
from src.modules.camera.models import Camera

logger = logging.getLogger(__name__)


def build_stream_url(camera: Camera) -> str:
    """Build stream URL từ DB fields.

    Ưu tiên rtsp_url, fallback stream_url (MJPEG từ Live Cam).
    Nếu camera có username/password, inject vào URL:
      rtsp://user:pass@host/stream
    """
    url = (camera.rtsp_url or "").strip()
    if not url:
        # Fallback: dùng stream_url nếu rtsp_url trống
        url = (camera.stream_url or "").strip()
    if not url:
        return ""

    # Nếu có auth credentials, inject vào URL
    if camera.username:
        parsed = urlparse(url)
        # Rebuild với userinfo
        netloc = parsed.netloc
        if "@" in netloc:
            # Đã có auth, thay thế
            netloc = netloc.split("@", 1)[1]
        auth = camera.username
        if camera.password_encrypted:
            # Tạm thời dùng password plain-text (TODO: Fernet decrypt)
            auth += f":{camera.password_encrypted}"
        netloc = f"{auth}@{netloc}"
        url = urlunparse(parsed._replace(netloc=netloc))

    return url


def auto_fix_url(url: str, stream_type: str = "rtsp") -> str:
    """Tự sửa URL cơ bản: thêm protocol nếu thiếu, append path nếu trống."""
    if not url:
        return url

    url = url.strip()

    # Thêm protocol nếu thiếu
    if not any(url.startswith(p) for p in ("http://", "https://", "rtsp://", "rtmp://")):
        url = f"{stream_type}://{url}"

    parsed = urlparse(url)
    if not parsed.path or parsed.path == "/":
        if stream_type in ("http", "rtmp"):
            url = url.rstrip("/") + "/video"
        elif stream_type == "rtsp":
            # RTSP thường có sẵn path, nhưng nếu trống thì thêm /stream
            url = url.rstrip("/") + "/stream"

    return url


class CameraConnection:
    """Một kết nối camera đơn lẻ — quản lý read loop + auto-reconnect."""

    def __init__(self, camera_id: int, camera: Camera, broadcast_callback):
        self.camera_id = camera_id
        self.camera = camera
        self.broadcast = broadcast_callback     # async fn(camera_id, data)
        self.is_running = False
        self.is_reconnecting = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.stream_url = ""
        self._task: Optional[asyncio.Task] = None
        self._reconnect_count = 0
        self._last_frame_time = 0.0
        self._total_frames = 0
        self._connected_since: Optional[datetime] = None

    async def start(self):
        """Kết nối camera và bắt đầu read loop."""
        self.stream_url = build_stream_url(self.camera)
        if not self.stream_url:
            logger.error(f"Camera {self.camera_id}: empty stream URL")
            return

        self.stream_url = auto_fix_url(self.stream_url, self.camera.stream_type)
        self.is_running = True
        self._reconnect_count = 0
        self._task = asyncio.create_task(self._main_loop())
        logger.info(f"Camera {self.camera_id}: started — {self.stream_url}")

    async def stop(self):
        """Dừng kết nối."""
        self.is_running = False
        self.is_reconnecting = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._release_capture()
        logger.info(f"Camera {self.camera_id}: stopped")

    def _release_capture(self):
        """Giải phóng cv2.VideoCapture."""
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    async def _main_loop(self):
        """Main loop: kết nối → read frames → detect → reconnect khi mất kết nối."""
        while self.is_running:
            # Thử kết nối
            connected = await self._connect()
            if not connected:
                if not self.is_running:
                    break
                # Chờ reconnect interval rồi thử lại
                await self._handle_reconnect()
                continue

            # Đã kết nối — chạy read loop
            self._reconnect_count = 0
            try:
                await self._read_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Camera {self.camera_id}: read loop error: {e}")

            # Read loop thoát = mất kết nối
            if self.is_running:
                await self._handle_reconnect()

    async def _connect(self) -> bool:
        """Thử kết nối đến camera. Returns True nếu thành công."""
        max_retries = min(self.camera.max_reconnect_attempts or 3, 5)
        timeout_ms = (self.camera.connect_timeout or 10) * 1000

        for attempt in range(1, max_retries + 1):
            if not self.is_running:
                return False

            logger.info(f"Camera {self.camera_id}: connecting attempt {attempt}/{max_retries}")

            try:
                # Mở capture trong thread để không block event loop
                cap = await asyncio.to_thread(cv2.VideoCapture, self.stream_url)
                if not cap or not cap.isOpened():
                    logger.warning(f"Camera {self.camera_id}: VideoCapture not opened")
                    if cap:
                        cap.release()
                    await asyncio.sleep(1)
                    continue

                # Set timeouts
                try:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
                except Exception:
                    pass  # Một số build OpenCV không hỗ trợ

                # Test đọc 1 frame
                ret, frame = await asyncio.to_thread(cap.read)
                if not ret or frame is None:
                    logger.warning(f"Camera {self.camera_id}: test frame read failed")
                    cap.release()
                    await asyncio.sleep(1)
                    continue

                # Thành công!
                self.cap = cap
                self._connected_since = datetime.utcnow()
                self.is_reconnecting = False

                # Notify frontend
                h, w = frame.shape[:2]
                await self.broadcast(self.camera_id, {
                    "status": "connected",
                    "message": f"Đã kết nối camera. Resolution: {w}x{h}",
                    "camera_id": self.camera_id,
                })
                return True

            except Exception as e:
                logger.error(f"Camera {self.camera_id}: connect error: {e}")
                await asyncio.sleep(1)

        return False

    async def _read_loop(self):
        """Loop đọc frame từ camera, chạy detect, broadcast kết quả."""
        from src.modules.detection.ai.pipeline import init_lpr_service
        from src.modules.detection.ai.tracking import CentroidTracker
        from src.modules.detection.ai.validation import is_valid_plate, get_plate_format_score

        service = init_lpr_service()
        centroid_tracker = CentroidTracker()
        frame_interval = 1.0 / max(self.camera.fps_target or 10, 1)
        ws_frame_idx = 0
        frame_timeout_count = 0
        max_frame_timeout = 50

        logger.info(f"Camera {self.camera_id}: entering read loop at {self.camera.fps_target} FPS")

        while self.is_running:
            frame_start = time.time()

            # Đọc frame
            ret, frame_bgr = await asyncio.to_thread(self.cap.read)

            if not ret or frame_bgr is None:
                frame_timeout_count += 1
                if frame_timeout_count >= max_frame_timeout:
                    logger.warning(f"Camera {self.camera_id}: frame timeout — no frames for ~5s")
                    await self.broadcast(self.camera_id, {
                        "status": "error",
                        "message": "Mất tín hiệu camera — đang thử kết nối lại...",
                        "camera_id": self.camera_id,
                    })
                    break
                await asyncio.sleep(0.1)
                continue

            frame_timeout_count = 0
            ws_frame_idx += 1
            self._total_frames += 1

            try:
                # Convert BGR → RGB → PIL
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

                # Resize cho frontend display (giữ bản gốc cho YOLO)
                h, w = frame_bgr.shape[:2]
                max_display_width = 640
                display_w = min(w, max_display_width)
                display_h = int(h * display_w / w) if w > 0 else h
                display_frame = cv2.resize(frame_bgr, (display_w, display_h))
                _, buffer = cv2.imencode(".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                frame_base64 = buffer.tobytes()

                # YOLO inference — chạy trên frame gốc (full resolution)
                conf1 = 0.5
                conf2 = 0.5
                conf3 = 0.3
                results = await asyncio.to_thread(
                    service, pil_img, conf1, conf2, conf3, "video", 640
                )

                # Filter valid plates
                valid_plates = []
                for r in (results or []):
                    text = r.get("plate_text") or r.get("text") or ""
                    if not text or text == "???" or "?" in text:
                        continue
                    if not is_valid_plate(text):
                        continue
                    if get_plate_format_score(text) <= 0:
                        continue
                    valid_plates.append({
                        "text": text,
                        "conf": r.get("confidence", 0),
                        "bbox": r.get("bbox", []),
                        "char_confs": r.get("character_confidences", []),
                    })

                # Centroid tracking
                finalized = centroid_tracker.update(
                    valid_plates, frame_idx=ws_frame_idx, frame_img=pil_img
                )

                # Get active plates for live display
                active_plates = centroid_tracker.get_active_plates()
                active_simple = [
                    {"text": p.get("text", ""), "conf": 0, "bbox": p.get("bbox", []), "hit_count": p.get("hit_count", 0)}
                    for p in (active_plates or [])
                ]

                # Broadcast kết quả
                finalized_simple = [
                    {k: v for k, v in r.items() if k not in ("first_frame_img", "best_frame_img")}
                    for r in (finalized or [])
                ]
                import base64
                await self.broadcast(self.camera_id, {
                    "status": "success",
                    "results": finalized_simple,
                    "active_plates": active_simple,
                    "frame": base64.b64encode(frame_base64).decode("utf-8"),
                    "frame_size": {"width": display_w, "height": display_h},
                    "camera_id": self.camera_id,
                    "total_frames": self._total_frames,
                })

            except Exception as e:
                logger.error(f"Camera {self.camera_id}: frame processing error: {e}")

            # Frame rate limiting
            elapsed = time.time() - frame_start
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def _handle_reconnect(self):
        """Xử lý auto-reconnect khi mất kết nối."""
        self._release_capture()
        self._reconnect_count += 1
        max_attempts = self.camera.max_reconnect_attempts or 10

        if self._reconnect_count > max_attempts:
            logger.error(f"Camera {self.camera_id}: max reconnect attempts ({max_attempts}) reached")
            await self.broadcast(self.camera_id, {
                "status": "error",
                "message": f"Không thể kết nối camera sau {max_attempts} lần thử. Vui lòng kiểm tra camera.",
                "camera_id": self.camera_id,
                "fatal": True,
            })
            self.is_running = False
            return

        self.is_reconnecting = True
        interval = self.camera.reconnect_interval or 5
        logger.info(
            f"Camera {self.camera_id}: reconnecting ({self._reconnect_count}/{max_attempts}) "
            f"in {interval}s..."
        )
        await self.broadcast(self.camera_id, {
            "status": "reconnecting",
            "message": f"Mất kết nối — thử lại ({self._reconnect_count}/{max_attempts})...",
            "camera_id": self.camera_id,
            "attempt": self._reconnect_count,
            "max_attempts": max_attempts,
        })
        await asyncio.sleep(interval)


class CameraConnectionManager:
    """Singleton quản lý tất cả IP camera connections đang hoạt động.

    Sử dụng:
        manager = get_connection_manager()
        await manager.connect_camera(camera_id, db, broadcast_fn)
        await manager.disconnect_camera(camera_id)
    """

    def __init__(self):
        self._connections: dict[int, CameraConnection] = {}
        self._broadcast_callback = None

    def set_broadcast_callback(self, callback):
        """Đặt callback để broadcast frames/results tới WebSocket clients."""
        self._broadcast_callback = callback

    async def connect_camera(self, camera_id: int, db: Session) -> bool:
        """Kết nối camera từ DB record."""
        if camera_id in self._connections and self._connections[camera_id].is_running:
            logger.info(f"Camera {camera_id}: already connected")
            return True

        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            logger.error(f"Camera {camera_id}: not found in DB")
            return False

        if not camera.rtsp_url and not camera.stream_url:
            logger.error(f"Camera {camera_id}: both rtsp_url and stream_url are empty")
            return False

        conn = CameraConnection(
            camera_id=camera_id,
            camera=camera,
            broadcast_callback=self._broadcast_callback,
        )
        self._connections[camera_id] = conn
        await conn.start()
        return True

    async def disconnect_camera(self, camera_id: int):
        """Ngắt kết nối camera."""
        conn = self._connections.get(camera_id)
        if conn:
            await conn.stop()
            del self._connections[camera_id]

    async def disconnect_all(self):
        """Ngắt tất cả camera connections."""
        for camera_id in list(self._connections.keys()):
            await self.disconnect_camera(camera_id)

    def get_connection(self, camera_id: int) -> Optional[CameraConnection]:
        """Lấy connection object của camera."""
        return self._connections.get(camera_id)

    def get_all_active(self) -> list[dict]:
        """Danh sách camera đang kết nối."""
        result = []
        for camera_id, conn in self._connections.items():
            result.append({
                "camera_id": camera_id,
                "is_running": conn.is_running,
                "is_reconnecting": conn.is_reconnecting,
                "stream_url": conn.stream_url,
                "total_frames": conn._total_frames,
                "connected_since": conn._connected_since.isoformat() if conn._connected_since else None,
                "reconnect_count": conn._reconnect_count,
            })
        return result

    def is_connected(self, camera_id: int) -> bool:
        """Kiểm tra camera có đang kết nối không."""
        conn = self._connections.get(camera_id)
        return conn is not None and conn.is_running


# Singleton instance
_manager: Optional[CameraConnectionManager] = None


def get_connection_manager() -> CameraConnectionManager:
    """Lấy singleton CameraConnectionManager."""
    global _manager
    if _manager is None:
        _manager = CameraConnectionManager()
    return _manager
