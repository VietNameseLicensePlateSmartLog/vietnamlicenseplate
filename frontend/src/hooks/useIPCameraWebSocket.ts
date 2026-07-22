'use client';

/**
 * useIPCameraWebSocket — Hook quản lý kết nối IP camera qua WebSocket.
 *
 * Khác với useWebSocket (webcam): hook này gửi camera_id thay vì frame,
 * backend tự đọc RTSP stream và gửi lại frame + detection results.
 *
 * Tính năng:
 * - Auto-reconnect với exponential backoff
 * - Status tracking (connecting / connected / reconnecting / error)
 * - Cleanup on unmount
 */
import { useRef, useCallback, useEffect, useState } from 'react';
import { WS_IP_URL } from '@/lib/api';

interface PlateResult {
  bbox: number[];
  text: string;
  conf: number;
  hit_count?: number;
}

interface FrameSize {
  width: number;
  height: number;
}

export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error';

interface UseIPCameraWebSocketOptions {
  onResults: (results: PlateResult[], activePlates?: PlateResult[]) => void;
  onFrame: (base64Frame: string, frameSize: FrameSize) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  onError?: (message: string) => void;
}

const MAX_RECONNECT = 5;
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

export function useIPCameraWebSocket({
  onResults,
  onFrame,
  onStatusChange,
  onError,
}: UseIPCameraWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const manualCloseRef = useRef(false);
  const cameraIdRef = useRef<number | null>(null);
  const configRef = useRef<{ conf1: number; conf2: number; conf3: number; regionId: number | null }>({
    conf1: 0.5, conf2: 0.5, conf3: 0.3, regionId: null,
  });

  // Refs cho callbacks (tránh stale closures)
  const onResultsRef = useRef(onResults);
  const onFrameRef = useRef(onFrame);
  const onStatusChangeRef = useRef(onStatusChange);
  const onErrorRef = useRef(onError);
  onResultsRef.current = onResults;
  onFrameRef.current = onFrame;
  onStatusChangeRef.current = onStatusChange;
  onErrorRef.current = onError;

  const updateStatus = useCallback((newStatus: ConnectionStatus) => {
    setStatus(newStatus);
    onStatusChangeRef.current?.(newStatus);
  }, []);

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback((cameraId: number, conf1 = 0.5, conf2 = 0.5, conf3 = 0.3, regionId: number | null = null) => {
    // Nếu đã kết nối camera này rồi thì bỏ qua
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && cameraIdRef.current === cameraId) {
      return;
    }

    // Cleanup kết nối cũ
    cleanup();
    manualCloseRef.current = false;
    cameraIdRef.current = cameraId;
    configRef.current = { conf1, conf2, conf3, regionId };
    reconnectTimerRef.current = null;

    updateStatus('connecting');
    setReconnectAttempt(0);

    console.log(`🔌 IP Camera: đang kết nối camera #${cameraId}...`);

    const ws = new WebSocket(WS_IP_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`✅ IP Camera WebSocket opened, sending config for camera #${cameraId}`);

      let userId: number | null = null;
      if (typeof window !== 'undefined') {
        const saved = localStorage.getItem('userId');
        if (saved) userId = parseInt(saved, 10);
      }

      // Gửi config (camera_id thay vì camera_url)
      ws.send(JSON.stringify({
        camera_id: cameraId,
        conf1,
        conf2,
        conf3,
        user_id: userId,
        region_id: regionId,
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.status) {
          case 'connected':
            console.log('✅ IP Camera connected:', data.message);
            updateStatus('connected');
            setReconnectAttempt(0);
            break;

          case 'success':
            // Frame + detection results
            if (data.frame) {
              const frameSize = data.frame_size || { width: 640, height: 480 };
              onFrameRef.current(data.frame, frameSize);
            }
            if (data.results || data.active_plates) {
              onResultsRef.current(data.results || [], data.active_plates);
            }
            break;

          case 'reconnecting':
            console.log(`🔄 IP Camera reconnecting (${data.attempt}/${data.max_attempts})...`);
            updateStatus('reconnecting');
            setReconnectAttempt(data.attempt || 0);
            break;

          case 'error':
            console.error('❌ IP Camera error:', data.message);
            if (data.fatal) {
              updateStatus('error');
            }
            onErrorRef.current?.(data.message);
            break;

          default:
            console.log('IP Camera unknown status:', data.status);
        }
      } catch (e) {
        console.error('Lỗi parse IP Camera message:', e);
      }
    };

    ws.onerror = (err) => {
      console.error('❌ IP Camera WebSocket error');
      onErrorRef.current?.('Lỗi kết nối WebSocket.');
    };

    ws.onclose = (event) => {
      console.log(`🔌 IP Camera WebSocket closed (code=${event.code})`);
      wsRef.current = null;

      if (!manualCloseRef.current) {
        // Auto reconnect
        const attempt = reconnectAttempt + 1;
        if (attempt < MAX_RECONNECT) {
          const delay = RECONNECT_DELAYS[attempt - 1] || RECONNECT_DELAYS[RECONNECT_DELAYS.length - 1];
          updateStatus('reconnecting');
          setReconnectAttempt(attempt);
          console.log(`🔄 IP Camera: thử lại (${attempt}/${MAX_RECONNECT}) sau ${delay}ms`);
          reconnectTimerRef.current = setTimeout(() => {
            if (!manualCloseRef.current && cameraIdRef.current) {
              const cfg = configRef.current;
              connect(cameraIdRef.current, cfg.conf1, cfg.conf2, cfg.conf3, cfg.regionId);
            }
          }, delay);
        } else {
          updateStatus('error');
          onErrorRef.current?.('Không thể kết nối camera sau nhiều lần thử.');
        }
      } else {
        updateStatus('idle');
      }
    };
  }, [cleanup, updateStatus, reconnectAttempt]);

  const disconnect = useCallback(() => {
    manualCloseRef.current = true;
    cameraIdRef.current = null;
    cleanup();
    updateStatus('idle');
    setReconnectAttempt(0);
  }, [cleanup, updateStatus]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      manualCloseRef.current = true;
      cleanup();
    };
  }, [cleanup]);

  return {
    connect,
    disconnect,
    status,
    reconnectAttempt,
    wsRef,
  };
}
