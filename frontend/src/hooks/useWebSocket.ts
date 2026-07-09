'use client';

import { useRef, useCallback, useEffect, useState } from 'react';
import { WS_URL } from '@/lib/api';

interface PlateResult {
  bbox: number[];
  text: string;
  conf: number;
}

interface UseWebSocketOptions {
  onResults: (results: PlateResult[], activePlates?: PlateResult[]) => void;
  onError?: (message: string) => void;
  onFirstResult?: () => void;
  onConnected?: () => void;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000]; // exponential backoff

export function useWebSocket({ onResults, onError, onFirstResult, onConnected }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const manualCloseRef = useRef(false);
  const [isConnected, setIsConnected] = useState(false);
  const firstResultFiredRef = useRef(false);

  // Use refs for callbacks to avoid stale closures
  const onResultsRef = useRef(onResults);
  const onErrorRef = useRef(onError);
  const onFirstResultRef = useRef(onFirstResult);
  const onConnectedRef = useRef(onConnected);
  onResultsRef.current = onResults;
  onErrorRef.current = onError;
  onFirstResultRef.current = onFirstResult;
  onConnectedRef.current = onConnected;

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent reconnect on manual close
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    // Don't connect if already connected
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return wsRef.current;
    }

    // Clean up previous connection
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    manualCloseRef.current = false;
    firstResultFiredRef.current = false;

    console.log(`🔌 Đang kết nối WebSocket: ${WS_URL}`);

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ WebSocket đã kết nối thành công');
      setIsConnected(true);
      reconnectAttemptRef.current = 0; // reset on success
      onConnectedRef.current?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status === 'success') {
          if (!firstResultFiredRef.current) {
            firstResultFiredRef.current = true;
            onFirstResultRef.current?.();
          }
          onResultsRef.current(data.results, data.active_plates);
        } else {
          console.error('WebSocket server lỗi:', data.message);
          onErrorRef.current?.(data.message);
        }
      } catch (e) {
        console.error('Lỗi parse WebSocket message:', e);
      }
    };

    ws.onerror = (err) => {
      console.error('❌ WebSocket lỗi kết nối:', WS_URL);
      onErrorRef.current?.(`Không thể kết nối đến backend tại ${WS_URL}`);
    };

    ws.onclose = (event) => {
      console.log(`🔌 WebSocket đóng (code=${event.code}, reason=${event.reason})`);
      setIsConnected(false);
      wsRef.current = null;

      // Auto reconnect if not manual close and haven't exceeded max attempts
      if (!manualCloseRef.current && reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = RECONNECT_DELAYS[reconnectAttemptRef.current] || RECONNECT_DELAYS[RECONNECT_DELAYS.length - 1];
        reconnectAttemptRef.current++;
        console.log(`🔄 Thử kết nối lại (${reconnectAttemptRef.current}/${MAX_RECONNECT_ATTEMPTS}) sau ${delay}ms...`);
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else if (reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        console.error('❌ Đã thử kết nối lại tối đa, dừng reconnect');
        onErrorRef.current?.('Không thể kết nối đến backend. Hãy chắc chắn backend đang chạy.');
      }
    };

    return ws;
  }, []);

  const disconnect = useCallback(() => {
    manualCloseRef.current = true;
    cleanup();
  }, [cleanup]);

  const sendFrame = useCallback((base64Data: string, conf1 = 0.5, conf2 = 0.5, conf3 = 0.3, regionId: number | null = null) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    let userId: number | null = null;
    if (typeof window !== 'undefined') {
      const savedUserId = localStorage.getItem('userId');
      if (savedUserId) {
        userId = parseInt(savedUserId, 10);
      }
    }

    wsRef.current.send(JSON.stringify({
      image: base64Data,
      conf1,
      conf2,
      conf3,
      user_id: userId,
      region_id: regionId,
    }));
  }, []);

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
    sendFrame,
    isConnected,
    wsRef,
  };
}
