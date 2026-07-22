'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useIPCameraWebSocket, ConnectionStatus } from '@/hooks/useIPCameraWebSocket';
import { API_BASE } from '@/lib/api';
import SnapshotModal from './SnapshotModal';

interface PlateResult {
  bbox: number[];
  text: string;
  conf: number;
}

interface HistoryRecord {
  id: string;
  plateText: string;
  startTime: Date;
  endTime: Date;
  maxConf: number;
  snapshot: string;
}

interface ActivePlate {
  recordId: string;
  lastSeen: number;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('vi-VN', { hour12: false });
}

function isSimilarPlate(p1: string, p2: string): boolean {
  const clean1 = p1.replace(/[-.]/g, '').toUpperCase();
  const clean2 = p2.replace(/[-.]/g, '').toUpperCase();

  if (clean1 === clean2) return true;
  if (Math.abs(clean1.length - clean2.length) > 1) return false;

  let diffCount = 0;
  const maxLen = Math.max(clean1.length, clean2.length);
  for (let i = 0; i < maxLen; i++) {
    if (clean1[i] !== clean2[i]) {
      diffCount++;
    }
  }
  return diffCount <= 1;
}

export default function RealtimeTab() {
  const [cameras, setCameras] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showPlaceholder, setShowPlaceholder] = useState(true);
  const [placeholderContent, setPlaceholderContent] = useState<'idle' | 'connecting'>('idle');
  const [historyRecords, setHistoryRecords] = useState<HistoryRecord[]>([]);
  const [modalRecord, setModalRecord] = useState<HistoryRecord | null>(null);
  const [systemCameras, setSystemCameras] = useState<{ id: number; name: string }[]>([]);
  const [selectedSystemCameraId, setSelectedSystemCameraId] = useState<number | null>(null);

  // ── IP Camera mode state ──
  const [cameraMode, setCameraMode] = useState<'webcam' | 'ip'>('webcam');
  const [ipCameras, setIpCameras] = useState<{ id: number; name: string; rtsp_url: string; stream_url: string; stream_type: string; is_online: boolean; region_name: string | null }[]>([]);
  const [selectedIpCameraId, setSelectedIpCameraId] = useState<number | null>(null);
  const [ipError, setIpError] = useState('');
  const ipFrameImageRef = useRef<HTMLImageElement | null>(null);

  const webcamVideoRef = useRef<HTMLVideoElement>(null);
  const realtimeCanvasRef = useRef<HTMLCanvasElement>(null);
  const hiddenCanvasRef = useRef<HTMLCanvasElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const isStreamingRef = useRef(false);
  const activePlatesRef = useRef<Record<string, ActivePlate>>({});
  const historyRecordsRef = useRef<HistoryRecord[]>([]);
  const currentDetectionsRef = useRef<PlateResult[]>([]);
  const sentFrameSizeRef = useRef({ width: 640, height: 480 });
  const drawLoopActiveRef = useRef(false);
  const sendSingleFrameRef = useRef<() => void>(() => {});
  const [detectionEnabled, setDetectionEnabled] = useState(false);
  const detectionEnabledRef = useRef(false);

  // Lắng nghe kết quả nhận dạng từ WebSocket
  // results = finalized plates (đã lưu DB, hiển thị history)
  // activePlates = các biển đang track (hiển thị live bbox)
  const handleResults = useCallback((results: PlateResult[], activePlates?: PlateResult[]) => {
    // Dùng activePlates cho live bbox (nếu có), nếu không thì dùng results
    const displayPlates = activePlates && activePlates.length > 0 ? activePlates : results;
    currentDetectionsRef.current = displayPlates;
    processRealtimeDetections(results);
    // Gửi frame tiếp theo sau ~200ms → target ~4 FPS
    if (isStreamingRef.current) {
      setTimeout(sendSingleFrameRef.current, 200);
    }
  }, []);

  const handleFirstResult = useCallback(() => {
    setShowPlaceholder(false);
  }, []);

  // Khi WebSocket kết nối thành công, bắt đầu gửi frame
  const handleConnected = useCallback(() => {
    if (!detectionEnabledRef.current) return;
    console.log('WebSocket connected, bắt đầu gửi frame');
    sendSingleFrameRef.current();
  }, []);

  const { connect, disconnect, sendFrame } = useWebSocket({
    onResults: handleResults,
    onFirstResult: handleFirstResult,
    onConnected: handleConnected,
  });

  // IP Camera WebSocket hook
  const handleIpFrame = useCallback((base64Frame: string, frameSize: { width: number; height: number }) => {
    sentFrameSizeRef.current = frameSize;
    if (ipFrameImageRef.current) {
      ipFrameImageRef.current.src = `data:image/jpeg;base64,${base64Frame}`;
    }
  }, []);

  const handleIpResults = useCallback((results: PlateResult[], activePlates?: PlateResult[]) => {
    const displayPlates = activePlates && activePlates.length > 0 ? activePlates : results;
    currentDetectionsRef.current = displayPlates;
    processRealtimeDetections(results);
  }, []);

  const handleIpStatusChange = useCallback((newStatus: ConnectionStatus) => {
    if (newStatus === 'connected') {
      setShowPlaceholder(false);
      setIpError('');
    } else if (newStatus === 'error') {
      // Error message handled by onError
    } else if (newStatus === 'idle') {
      setShowPlaceholder(true);
    }
  }, []);

  const handleIpError = useCallback((message: string) => {
    setIpError(message);
  }, []);

  const ipCameraWs = useIPCameraWebSocket({
    onResults: handleIpResults,
    onFrame: handleIpFrame,
    onStatusChange: handleIpStatusChange,
    onError: handleIpError,
  });

  // Load cameras khi component mount — tự động xin quyền nếu chưa có
  useEffect(() => {
    loadCameras();
  }, []);

  // Load danh sách IP cameras từ backend
  useEffect(() => {
    fetch(`${API_BASE}/cameras`)
      .then(res => res.ok ? res.json() : [])
      .then(data => {
        if (Array.isArray(data)) {
          setSystemCameras(data.map((c: any) => ({ id: c.id, name: c.name })));
          setIpCameras(data.filter((c: any) => c.rtsp_url || c.stream_url).map((c: any) => ({
            id: c.id,
            name: c.name,
            rtsp_url: c.rtsp_url || '',
            stream_url: c.stream_url || '',
            stream_type: c.stream_type || 'rtsp',
            is_online: c.is_online,
            region_name: c.region_name,
          })));
        }
      })
      .catch(() => {});
  }, []);

  // Quản lý WebSocket dựa trên detectionEnabled — chỉ connect webcam WS khi ở webcam mode
  useEffect(() => {
    detectionEnabledRef.current = detectionEnabled;
    if (!isStreamingRef.current) return;
    // IP camera mode có WebSocket riêng, không dùng webcam WS
    if (cameraMode === 'ip') return;

    if (detectionEnabled) {
      connect();
    } else {
      disconnect();
      currentDetectionsRef.current = [];
    }
  }, [detectionEnabled, connect, disconnect, cameraMode]);

  // Toggle nhận diện
  const toggleDetection = useCallback(() => {
    setDetectionEnabled(prev => !prev);
  }, []);

  async function loadCameras(): Promise<MediaDeviceInfo[]> {
    try {
      // Bước1: Thử enumerate không xin quyền
      let devices = await navigator.mediaDevices.enumerateDevices();
      let videoDevices = devices.filter((d) => d.kind === 'videoinput');

      // Bước2: Nếu chưa có quyền (label rỗng), xin quyền camera
      const needsPermission = videoDevices.length === 0 || videoDevices.every(d => !d.label);
      if (needsPermission) {
        try {
          const tempStream = await navigator.mediaDevices.getUserMedia({ video: true });
          // Thành công → tắt ngay, enumerate lại để lấy label
          tempStream.getTracks().forEach(t => t.stop());
          devices = await navigator.mediaDevices.enumerateDevices();
          videoDevices = devices.filter((d) => d.kind === 'videoinput');
        } catch (permErr) {
          console.warn('User từ chối quyền camera:', permErr);
        }
      }

      setCameras(videoDevices);
      if (videoDevices.length > 0 && !selectedDeviceId) {
        setSelectedDeviceId(videoDevices[0].deviceId);
      }
      return videoDevices;
    } catch (err) {
      console.warn('Không thể liệt kê thiết bị camera:', err);
      return [];
    }
  }

  // Vẽ frame mượt trên canvas 30fps
  const startLocalDrawingLoop = useCallback(() => {
    const canvas = realtimeCanvasRef.current;
    const video = webcamVideoRef.current;
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    drawLoopActiveRef.current = true;

    function drawFrame() {
      if (!isStreamingRef.current || !drawLoopActiveRef.current) return;

      if (video!.readyState === video!.HAVE_ENOUGH_DATA) {
        if (canvas!.width !== video!.videoWidth) {
          canvas!.width = video!.videoWidth;
          canvas!.height = video!.videoHeight;
        }

        ctx!.drawImage(video!, 0, 0, canvas!.width, canvas!.height);
        if (detectionEnabledRef.current) {
          drawDetectionsOnCanvas(ctx!, canvas!);
        }
      }

      requestAnimationFrame(drawFrame);
    }

    requestAnimationFrame(drawFrame);
  }, []);

  function drawDetectionsOnCanvas(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement) {
    const detections = currentDetectionsRef.current;
    if (!detections || detections.length === 0) return;

    const colors = ['#00FF00', '#FF8C00', '#00FFFF', '#FF00FF', '#FFFF00'];

    detections.forEach((plate, i) => {
      const bbox = plate.bbox;
      if (!bbox || bbox.length !== 4) return;

      const scaleX = canvas.width / sentFrameSizeRef.current.width;
      const scaleY = canvas.height / sentFrameSizeRef.current.height;

      const x1 = bbox[0] * scaleX;
      const y1 = bbox[1] * scaleY;
      const x2 = bbox[2] * scaleX;
      const y2 = bbox[3] * scaleY;

      const color = colors[i % colors.length];

      ctx.strokeStyle = color;
      ctx.lineWidth = 4;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Chỉ hiển thị text, không hiển thị confidence lúc real-time
      // Confidence chỉ tính khi biển biến mất (finalize)
      const label = `${plate.text}`;
      ctx.font = 'bold 16px Outfit, Inter, Arial';
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = color;
      ctx.fillRect(x1 - 2, y1 - 26, textWidth + 10, 26);

      ctx.fillStyle = '#000000';
      ctx.fillText(label, x1 + 3, y1 - 7);
    });
  }

  // Gửi một frame đơn lẻ sang server (dùng createImageBitmap để encode ngoài main thread)
  const sendSingleFrame = useCallback(async () => {
    if (!isStreamingRef.current || !detectionEnabledRef.current) return;

    const video = webcamVideoRef.current;
    const canvas = hiddenCanvasRef.current;
    if (!video || !canvas) return;
    if (video.readyState !== video.HAVE_ENOUGH_DATA) {
      setTimeout(sendSingleFrame, 30);
      return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const maxW = 640;
    const scale = Math.min(1, maxW / video.videoWidth);
    canvas.width = video.videoWidth * scale;
    canvas.height = video.videoHeight * scale;

    sentFrameSizeRef.current = { width: canvas.width, height: canvas.height };

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    try {
      const bitmap = await createImageBitmap(canvas);
      const offscreen = new OffscreenCanvas(bitmap.width, bitmap.height);
      const offCtx = offscreen.getContext('2d')!;
      offCtx.drawImage(bitmap, 0, 0);
      const blob = await offscreen.convertToBlob({ type: 'image/jpeg', quality: 0.6 });
      bitmap.close();
      const reader = new FileReader();
      reader.onloadend = () => {
        if (isStreamingRef.current && detectionEnabledRef.current && reader.result) {
          sendFrame(reader.result as string, 0.5, 0.5, 0.3, null, selectedSystemCameraId);
        }
      };
      reader.readAsDataURL(blob);
    } catch {
      // Fallback: toDataURL nếu createImageBitmap không hỗ trợ JPEG
      const base64Data = canvas.toDataURL('image/jpeg', 0.6);
      sendFrame(base64Data, 0.5, 0.5, 0.3, null, selectedSystemCameraId);
    }
  }, [sendFrame, selectedSystemCameraId]);

  // Sync ref để handleResults/handleConnected có thể gọi qua ref
  sendSingleFrameRef.current = sendSingleFrame;

  // Tạo ảnh chụp snapshot có vẽ khung nhận diện chính xác với frame hình gửi đi
  const getAnnotatedSnapshot = useCallback((results: PlateResult[]) => {
    const canvas = hiddenCanvasRef.current;
    if (!canvas) return '';
    const ctx = canvas.getContext('2d');
    if (!ctx) return canvas.toDataURL('image/jpeg', 0.8);

    // Lưu lại trạng thái canvas trước khi vẽ đè
    ctx.save();

    const colors = ['#00FF00', '#FF8C00', '#00FFFF', '#FF00FF', '#FFFF00'];
    results.forEach((plate, i) => {
      const bbox = plate.bbox;
      if (!bbox || bbox.length !== 4) return;

      // Do hiddenCanvas chính là frame đã scale gửi đi, tọa độ bbox khớp 1:1
      const x1 = bbox[0];
      const y1 = bbox[1];
      const x2 = bbox[2];
      const y2 = bbox[3];

      const color = colors[i % colors.length];

      // Vẽ bounding box
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Vẽ nhãn văn bản biển số
      const label = `${plate.text} (${(plate.conf * 100).toFixed(2)}%)`;
      ctx.font = 'bold 12px Outfit, Inter, Arial';
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = color;
      ctx.fillRect(x1 - 2, y1 - 18, textWidth + 6, 18);

      ctx.fillStyle = '#000000';
      ctx.fillText(label, x1 + 1, y1 - 5);
    });

    const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
    ctx.restore();
    return dataUrl;
  }, []);

  // Xử lý logic theo dõi biển số (stable vì chỉ đọc refs)
  const processRealtimeDetections = useCallback((results: PlateResult[]) => {
    const now = Date.now();
    const activePlates = activePlatesRef.current;

    if (results && results.length > 0) {
      results.forEach((plate) => {
        const text = plate.text;
        const conf = plate.conf;
        if (!text || text.includes('?')) return;

        const cleanText = text.replace(/[-.\s]/g, '');
        if (cleanText.length < 8) return;

        let foundActiveText: string | null = null;
        for (const activeText in activePlates) {
          if (isSimilarPlate(text, activeText)) {
            foundActiveText = activeText;
            break;
          }
        }

        if (!foundActiveText) {
          const recordId = 'rec-' + now + '-' + Math.floor(Math.random() * 1000);
          const record: HistoryRecord = {
            id: recordId,
            plateText: text,
            startTime: new Date(),
            endTime: new Date(),
            maxConf: conf,
            snapshot: getAnnotatedSnapshot(results),
          };

          historyRecordsRef.current = [record, ...historyRecordsRef.current].slice(0, 50);
          setHistoryRecords([...historyRecordsRef.current]);

          activePlates[text] = { recordId, lastSeen: now };
        } else {
          const activeInfo = activePlates[foundActiveText];
          activeInfo.lastSeen = now;

          // Cập nhật confidence mới nhất cho record trong lịch sử
          const existingRecord = historyRecordsRef.current.find(r => r.id === activeInfo.recordId);
          if (existingRecord) {
            existingRecord.maxConf = conf;
            existingRecord.endTime = new Date();
            existingRecord.snapshot = getAnnotatedSnapshot(results);
            setHistoryRecords([...historyRecordsRef.current]);
          }
        }
      });
    }

    // Quét dọn biển số đã biến mất
    for (const text in activePlates) {
      if (now - activePlates[text].lastSeen > 2500) {
        delete activePlates[text];
      }
    }
  }, []);

  // Bắt đầu camera
  async function startCamera() {
    // Nếu chưa có camera nào, thử load lại — dùng return value để tránh stale state
    let devices = cameras;
    if (devices.length === 0) {
      devices = await loadCameras();
      if (devices.length === 0) {
        alert('Không tìm thấy camera nào.\n\nKiểm tra:\n1. Camera đã kết nối chưa?\n2. Đã cho phép quyền camera ở thanh địa chỉ?\n3. Không có app nào khác đang dùng camera?');
        return;
      }
    }

    // Chọn device ID: ưu tiên selectedDeviceId, nếu không có thì lấy device đầu tiên
    const deviceId = selectedDeviceId || devices[0].deviceId;
    const constraints = {
      video: { deviceId: { exact: deviceId } },
    };

    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      cameraStreamRef.current = stream;

      // Cập nhật lại danh sách camera (để lấy nhãn đầy đủ sau khi có quyền)
      try {
        const allDevices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = allDevices.filter((d) => d.kind === 'videoinput');
        if (videoDevices.length > 0) {
          setCameras(videoDevices);
        }
      } catch {
        // Không cần xử lý — danh sách camera cũ vẫn dùng được
      }

      if (webcamVideoRef.current) {
        webcamVideoRef.current.srcObject = stream;
      }

      // Hiển thị spinner chờ video load
      setShowPlaceholder(true);
      setPlaceholderContent('connecting');
      setIsStreaming(true);
      isStreamingRef.current = true;

      // Ẩn placeholder ngay khi video có data (không chờ WebSocket)
      const videoEl = webcamVideoRef.current;
      if (videoEl) {
        const hidePlaceholderOnVideoReady = () => {
          setShowPlaceholder(false);
        };
        // Dùng both events để cover edge cases
        videoEl.addEventListener('loadeddata', hidePlaceholderOnVideoReady, { once: true });
        // Fallback: nếu video đã sẵn sàng trước khi event fire
        if (videoEl.readyState >= 2) {
          setShowPlaceholder(false);
        }
      }

      // WebSocket và draw loop sẽ bắt đầu khi user bật nhận diện (detectionEnabled → true)
      startLocalDrawingLoop();
    } catch (err) {
      const error = err as Error;
      if (error.name === 'NotAllowedError') {
        alert('Bạn cần cấp quyền truy cập camera.\n\nCách sửa:\n- Nhấn icon camera 🔒 trên thanh địa chỉ\n- Chọn "Cho phép"\n- Thử lại');
      } else if (error.name === 'NotFoundError') {
        alert('Không tìm thấy camera nào.\n\nKiểm tra:\n1. Camera đã kết nối chưa?\n2. Driver camera đã cài đúng?\n3. Không có app nào khác đang chiếm camera?');
      } else if (error.name === 'NotReadableError') {
        alert('Camera đang bị chiếm bởi ứng dụng khác.\n\nĐóng các app đang dùng camera (Zoom, Teams, OBS...) rồi thử lại.');
      } else {
        alert('Lỗi camera: ' + error.name + '\n' + error.message);
      }
    }
  }

  // Tắt camera
  function stopCamera() {
    isStreamingRef.current = false;
    drawLoopActiveRef.current = false;
    detectionEnabledRef.current = false;
    setDetectionEnabled(false);
    currentDetectionsRef.current = [];
    setIsStreaming(false);

    disconnect();

    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
    }

    if (webcamVideoRef.current) {
      webcamVideoRef.current.srcObject = null;
    }

    setShowPlaceholder(true);
    setPlaceholderContent('idle');

    activePlatesRef.current = {};
    historyRecordsRef.current = [];
    setHistoryRecords([]);
  }

  // ════════════════════════════════════════════════════════════════════
  // IP Camera Mode
  // ════════════════════════════════════════════════════════════════════

  const ipDrawLoopActiveRef = useRef(false);

  // Vẽ frame IP camera lên canvas (continuous loop)
  const startIpDrawLoop = useCallback(() => {
    const canvas = realtimeCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ipDrawLoopActiveRef.current = true;

    function drawFrame() {
      if (!ipDrawLoopActiveRef.current) return;

      const img = ipFrameImageRef.current;
      if (img && img.complete && img.naturalWidth > 0) {
        if (canvas.width !== img.naturalWidth) {
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
        }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        if (detectionEnabledRef.current) {
          drawDetectionsOnCanvas(ctx, canvas);
        }
      }

      requestAnimationFrame(drawFrame);
    }

    requestAnimationFrame(drawFrame);
  }, []);

  // Kết nối IP camera từ dropdown (dùng hook)
  function connectIpCamera() {
    if (!selectedIpCameraId) {
      alert('Vui lòng chọn camera từ danh sách.');
      return;
    }

    setIpError('');
    setShowPlaceholder(true);

    // Pre-create Image element for frame rendering
    if (!ipFrameImageRef.current) {
      ipFrameImageRef.current = new Image();
    }

    // Kết nối qua hook — backend tự lấy URL từ DB dựa trên camera_id
    ipCameraWs.connect(selectedIpCameraId, 0.5, 0.5, 0.3, null);

    setIsStreaming(true);
    isStreamingRef.current = true;
    startIpDrawLoop();
  }

  // Ngắt kết nối IP camera
  function disconnectIpCamera() {
    ipDrawLoopActiveRef.current = false;
    isStreamingRef.current = false;
    detectionEnabledRef.current = false;
    setDetectionEnabled(false);
    currentDetectionsRef.current = [];
    setIsStreaming(false);

    ipCameraWs.disconnect();

    setShowPlaceholder(true);

    activePlatesRef.current = {};
    historyRecordsRef.current = [];
    setHistoryRecords([]);
  }

  // Chuyển đổi giữa Webcam ↔ IP Camera
  function switchCameraMode(mode: 'webcam' | 'ip') {
    if (mode === cameraMode) return;

    // Dừng session hiện tại nếu đang chạy
    if (isStreamingRef.current) {
      if (cameraMode === 'webcam') {
        stopCamera();
      } else {
        disconnectIpCamera();
      }
    }

    setCameraMode(mode);
    setIpError('');
    setSelectedIpCameraId(null);
  }

  const openModal = useCallback((recordId: string) => {
    const record = historyRecordsRef.current.find((r) => r.id === recordId);
    if (record) {
      setModalRecord(record);
    }
  }, []);

  const getModalTimeRange = useCallback(() => {
    if (!modalRecord) return '';
    const startStr = formatTime(modalRecord.startTime);
    const endStr = formatTime(modalRecord.endTime);
    if (startStr !== endStr) {
      const durationSec = Math.round((modalRecord.endTime.getTime() - modalRecord.startTime.getTime()) / 1000);
      return `${startStr} - ${endStr} (${durationSec} giây)`;
    }
    return `${startStr} (Đang xuất hiện)`;
  }, [modalRecord]);

  return (
    <>
      <section className="tab-content active">
        <div className="grid-layout realtime-grid">
          {/* Left: Webcam Control & Viewport */}
          <div className="card upload-card">
            <div className="card-header">
              <h2>Điều khiển Camera</h2>
              <p>Bật luồng nhận diện biển số thời gian thực từ camera hoạt động</p>
            </div>

            <div className="camera-actions-row mb-4">
              {cameraMode === 'webcam' ? (
                !isStreaming ? (
                  <button className="btn btn-primary btn-block" onClick={startCamera}>
                    <i className="fa-solid fa-play"></i> Bắt đầu Camera
                  </button>
                ) : (
                  <button className="btn btn-danger btn-block" onClick={stopCamera}>
                    <i className="fa-solid fa-stop"></i> Dừng Camera
                  </button>
                )
              ) : (
                // IP Camera mode: nút trạng thái (kết nối/ngắt ở sidebar)
                <div style={{
                  padding: '0.75rem 1rem', borderRadius: 8, textAlign: 'center', fontSize: '0.85rem',
                  background: ipCameraWs.status === 'connected' ? 'rgba(0,200,83,0.08)' : 'rgba(120,144,156,0.08)',
                  border: `1px solid ${ipCameraWs.status === 'connected' ? 'rgba(0,200,83,0.25)' : 'rgba(120,144,156,0.2)'}`,
                  color: 'var(--text-secondary)',
                }}>
                  {ipCameraWs.status === 'connected' ? (
                    <><i className="fa-solid fa-circle" style={{ color: '#00c853', marginRight: '0.4rem', fontSize: '0.6rem' }}></i> Đang kết nối IP Camera</>
                  ) : (
                    <><i className="fa-solid fa-circle" style={{ color: '#90a4ae', marginRight: '0.4rem', fontSize: '0.6rem' }}></i> Chọn camera ở panel bên phải để kết nối</>
                  )}
                </div>
              )}
            </div>

            {/* Toggle nhận diện — chỉ hiển thị khi camera đang chạy */}
            {isStreaming && (
              <div className="detection-toggle-row" style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem',
                padding: '0.75rem 1rem', borderRadius: 8,
                background: detectionEnabled ? 'rgba(0,200,83,0.08)' : 'rgba(120,144,156,0.08)',
                border: `1px solid ${detectionEnabled ? 'rgba(0,200,83,0.25)' : 'rgba(120,144,156,0.2)'}`,
                transition: 'all 0.2s ease',
              }}>
                <button
                  onClick={toggleDetection}
                  style={{
                    position: 'relative', width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
                    background: detectionEnabled ? '#00c853' : '#90a4ae',
                    transition: 'background 0.2s ease', flexShrink: 0,
                  }}
                >
                  <span style={{
                    position: 'absolute', top: 2, left: detectionEnabled ? 22 : 2,
                    width: 20, height: 20, borderRadius: '50%', background: '#fff',
                    transition: 'left 0.2s ease', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                  }} />
                </button>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                    <i className="fa-solid fa-microscope" style={{ marginRight: '0.4rem', color: detectionEnabled ? '#00c853' : '#90a4ae' }}></i>
                    Nhận diện biển số
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {detectionEnabled ? 'Đang nhận diện — camera có thể bị giật nhẹ' : 'Tắt — xem camera mượt 60fps'}
                  </span>
                </div>
              </div>
            )}

            {/* Hidden canvas for frame capture */}
            <canvas ref={hiddenCanvasRef} style={{ display: 'none' }}></canvas>

            {/* Viewport */}
            <div className="realtime-viewport-container mt-4">
              {showPlaceholder && (
                <div className="viewport-placeholder">
                  {placeholderContent === 'idle' ? (
                    <>
                      <i className="fa-solid fa-camera"></i>
                      <span>Chưa mở Camera</span>
                    </>
                  ) : (
                    <>
                      <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3, margin: '0 auto 1rem' }}></div>
                      <span>Đang kết nối camera...</span>
                    </>
                  )}
                </div>
              )}
              <video
                ref={webcamVideoRef}
                autoPlay
                playsInline
                style={{
                  width: '100%',
                  borderRadius: 8,
                  objectFit: 'contain',
                  display: showPlaceholder || detectionEnabled || cameraMode === 'ip' ? 'none' : 'block',
                }}
              ></video>
              <canvas
                ref={realtimeCanvasRef}
                id="realtime-canvas"
                style={{
                  display: showPlaceholder
                    ? 'none'
                    : (cameraMode === 'ip' ? 'block' : (detectionEnabled ? 'block' : 'none')),
                }}
              ></canvas>
            </div>
          </div>

          {/* Right Panel Column Stack */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            {/* Thẻ 1: Cấu hình Camera */}
            <div className="card">
              <div className="card-header" style={{ paddingBottom: '0.8rem' }}>
                <h2>Cấu hình Camera</h2>
                <p>Chọn nguồn camera đầu vào cho luồng xử lý thời gian thực</p>
              </div>
              <div style={{ padding: '0 1.5rem 1.5rem 1.5rem' }}>
                {/* Mode Toggle: Webcam | IP Camera */}
                <div style={{
                  display: 'flex', borderRadius: 8, overflow: 'hidden',
                  border: '1px solid rgba(120,144,156,0.25)', marginBottom: '1rem',
                }}>
                  <button
                    onClick={() => switchCameraMode('webcam')}
                    disabled={isStreaming}
                    style={{
                      flex: 1, padding: '0.6rem 0', border: 'none', cursor: isStreaming ? 'not-allowed' : 'pointer',
                      fontWeight: 600, fontSize: '0.82rem', transition: 'all 0.2s',
                      background: cameraMode === 'webcam' ? 'var(--primary, #6c5ce7)' : 'transparent',
                      color: cameraMode === 'webcam' ? '#fff' : 'var(--text-secondary, #90a4ae)',
                      opacity: isStreaming ? 0.6 : 1,
                    }}
                  >
                    <i className="fa-solid fa-camera" style={{ marginRight: '0.4rem' }}></i>
                    Webcam
                  </button>
                  <button
                    onClick={() => switchCameraMode('ip')}
                    disabled={isStreaming}
                    style={{
                      flex: 1, padding: '0.6rem 0', border: 'none', borderLeft: '1px solid rgba(120,144,156,0.25)',
                      cursor: isStreaming ? 'not-allowed' : 'pointer',
                      fontWeight: 600, fontSize: '0.82rem', transition: 'all 0.2s',
                      background: cameraMode === 'ip' ? 'var(--primary, #6c5ce7)' : 'transparent',
                      color: cameraMode === 'ip' ? '#fff' : 'var(--text-secondary, #90a4ae)',
                      opacity: isStreaming ? 0.6 : 1,
                    }}
                  >
                    <i className="fa-solid fa-network-wired" style={{ marginRight: '0.4rem' }}></i>
                    IP Camera
                  </button>
                </div>

                {/* ── Webcam Mode Config ── */}
                {cameraMode === 'webcam' && (
                  <>
                    <div className="form-group" style={{ margin: 0 }}>
                      <label htmlFor="camera-select" className="form-label" style={{ fontSize: '0.85rem' }}>
                        <i className="fa-solid fa-camera" style={{ color: 'var(--primary)', marginRight: '0.5rem' }}></i>
                        Thiết bị Camera hoạt động:
                      </label>
                      <select
                        id="camera-select"
                        className="form-select"
                        value={selectedDeviceId}
                        onChange={(e) => setSelectedDeviceId(e.target.value)}
                        disabled={isStreaming}
                      >
                        {cameras.length === 0 ? (
                          <option value="">Không tìm thấy camera nào</option>
                        ) : (
                          cameras.map((device, index) => (
                            <option key={device.deviceId} value={device.deviceId}>
                              {device.label || `Camera ${index + 1}`}
                            </option>
                          ))
                        )}
                      </select>
                    </div>

                    {/* Chọn camera IP (system camera) để gắn với kết quả nhận diện */}
                    {systemCameras.length > 0 && (
                      <div className="form-group" style={{ margin: 0, marginTop: '1rem' }}>
                        <label htmlFor="system-camera-select" className="form-label" style={{ fontSize: '0.85rem' }}>
                          <i className="fa-solid fa-video" style={{ color: 'var(--primary)', marginRight: '0.5rem' }}></i>
                          Gắn với Camera IP:
                        </label>
                        <select
                          id="system-camera-select"
                          className="form-select"
                          value={selectedSystemCameraId ?? ''}
                          onChange={(e) => setSelectedSystemCameraId(e.target.value ? Number(e.target.value) : null)}
                        >
                          <option value="">Không gắn camera</option>
                          {systemCameras.map(cam => (
                            <option key={cam.id} value={cam.id}>{cam.name}</option>
                          ))}
                        </select>
                      </div>
                    )}
                  </>
                )}

                {/* ── IP Camera Mode Config ── */}
                {cameraMode === 'ip' && (
                  <>
                    {/* Chọn camera từ danh sách DB */}
                    <div className="form-group" style={{ margin: 0 }}>
                      <label htmlFor="ip-camera-select" className="form-label" style={{ fontSize: '0.85rem' }}>
                        <i className="fa-solid fa-network-wired" style={{ color: 'var(--primary)', marginRight: '0.5rem' }}></i>
                        Chọn Camera IP:
                      </label>
                      <select
                        id="ip-camera-select"
                        className="form-select"
                        value={selectedIpCameraId ?? ''}
                        onChange={(e) => setSelectedIpCameraId(e.target.value ? Number(e.target.value) : null)}
                        disabled={ipCameraWs.status === 'connected' || ipCameraWs.status === 'reconnecting'}
                        style={{ fontSize: '0.85rem' }}
                      >
                        <option value="">-- Chọn camera --</option>
                        {ipCameras.map(cam => (
                          <option key={cam.id} value={cam.id}>
                            {cam.name} ({cam.stream_type.toUpperCase()}) {cam.is_online ? '🟢' : '⚪'}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Hiển thị thông tin camera đã chọn */}
                    {selectedIpCameraId && (() => {
                      const cam = ipCameras.find(c => c.id === selectedIpCameraId);
                      if (!cam) return null;
                      return (
                        <div style={{
                          marginTop: '0.75rem', padding: '0.6rem 0.8rem', borderRadius: 8,
                          background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)',
                          fontSize: '0.8rem',
                        }}>
                          <div style={{ color: '#60a5fa', fontWeight: 600, marginBottom: '4px' }}>{cam.name}</div>
                          <div style={{ color: '#94a3b8', fontSize: '0.75rem', wordBreak: 'break-all' }}>
                            {cam.rtsp_url || cam.stream_url || 'Chưa có URL'}
                          </div>
                          {cam.region_name && (
                            <div style={{ color: '#64748b', fontSize: '0.72rem', marginTop: '2px' }}>
                              Vùng: {cam.region_name}
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {/* Nút Kết nối / Ngắt kết nối */}
                    <div style={{ marginTop: '1rem' }}>
                      {ipCameraWs.status !== 'connected' && ipCameraWs.status !== 'reconnecting' ? (
                        <button
                          className="btn btn-primary btn-block"
                          onClick={connectIpCamera}
                          disabled={!selectedIpCameraId || ipCameraWs.status === 'connecting'}
                          style={{ opacity: !selectedIpCameraId || ipCameraWs.status === 'connecting' ? 0.6 : 1 }}
                        >
                          {ipCameraWs.status === 'connecting' ? (
                            <>
                              <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, display: 'inline-block', verticalAlign: 'middle', marginRight: '0.5rem' }}></div>
                              Đang kết nối...
                            </>
                          ) : (
                            <>
                              <i className="fa-solid fa-plug"></i> Kết nối Camera
                            </>
                          )}
                        </button>
                      ) : (
                        <button
                          className="btn btn-danger btn-block"
                          onClick={disconnectIpCamera}
                        >
                          <i className="fa-solid fa-stop"></i> Ngắt kết nối
                        </button>
                      )}
                    </div>

                    {/* Hiển thị lỗi / reconnecting status */}
                    {ipCameraWs.status === 'reconnecting' && (
                      <div style={{
                        marginTop: '0.75rem', padding: '0.6rem 0.8rem', borderRadius: 8,
                        background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.3)',
                        color: '#fbbf24', fontSize: '0.8rem',
                        display: 'flex', alignItems: 'center', gap: '0.5rem',
                      }}>
                        <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2, display: 'inline-block', borderColor: '#fbbf24', borderTopColor: 'transparent' }}></div>
                        Mất kết nối — đang thử lại ({ipCameraWs.reconnectAttempt}/5)...
                      </div>
                    )}
                    {ipError && ipCameraWs.status !== 'reconnecting' && (
                      <div style={{
                        marginTop: '0.75rem', padding: '0.6rem 0.8rem', borderRadius: 8,
                        background: 'rgba(239,83,80,0.1)', border: '1px solid rgba(239,83,80,0.3)',
                        color: '#ef5350', fontSize: '0.8rem',
                      }}>
                        <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '0.4rem' }}></i>
                        {ipError}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Thẻ 2: Lịch sử nhận diện thời gian thực */}
            <div className="card results-card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div className="card-header">
                <h2>Lịch sử nhận diện thời gian thực</h2>
                <p>Các biển số phát hiện được từ luồng stream camera trực tiếp</p>
              </div>

              <div className="realtime-history-container" style={{ flex: 1, overflowY: 'auto' }}>
                {historyRecords.length === 0 ? (
                  <div className="empty-state">
                    <i className="fa-solid fa-clock-rotate-left"></i>
                    <h3>Lịch sử trống</h3>
                    <p>Khi camera hoạt động, các biển số xe nhận diện được sẽ xuất hiện ở đây theo thời gian thực</p>
                  </div>
                ) : (
                  <div className="history-log">
                    {historyRecords.slice(0, 20).map((record) => {
                      const startStr = formatTime(record.startTime);
                      const endStr = formatTime(record.endTime);
                      const timeDisplay = startStr !== endStr ? `${startStr} - ${endStr}` : startStr;

                      return (
                        <div
                          key={record.id}
                          className="history-item"
                          onClick={() => openModal(record.id)}
                        >
                          <div className="history-info">
                            <span className="history-plate">{record.plateText}</span>
                            <div className="history-meta">
                              <span className="history-time">
                                <i className="fa-regular fa-clock"></i> {timeDisplay}
                              </span>
                              <span className="badge badge-conf">{(record.maxConf * 100).toFixed(2)}% Conf</span>
                            </div>
                          </div>
                          <span className="badge badge-text" title="Bấm để xem ảnh chụp">
                            <i className="fa-solid fa-image"></i>
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      </section>

      <SnapshotModal
        isOpen={!!modalRecord}
        onClose={() => setModalRecord(null)}
        plateText={modalRecord?.plateText || ''}
        timeRange={getModalTimeRange()}
        confidence={modalRecord?.maxConf || 0}
        snapshotSrc={modalRecord?.snapshot || ''}
      />
    </>
  );
}
