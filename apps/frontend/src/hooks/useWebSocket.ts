import { useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '../store/useAppStore';
import * as api from '../lib/api';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

type WSMessage = {
  type: string;
  data: Record<string, unknown>;
};

/**
 * Global WebSocket hook that connects once and listens for real-time events.
 * Updates the Zustand store when events arrive so all pages stay in sync.
 */
export function useGlobalWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const {
    setWsConnected,
    incrementWsReconnect,
    resetWsReconnect,
    setMetrics,
    setDataSources,
    setPipelines,
  } = useAppStore();

  const handleMessage = useCallback(async (message: WSMessage) => {
    switch (message.type) {
      case 'pong':
        break;
      case 'metrics':
        if (message.data) {
          setMetrics(message.data as any);
        }
        break;
      case 'pipeline_update':
        try {
          const pipelines = await api.listPipelines();
          setPipelines(pipelines);
        } catch (e) {
          console.warn('[WS] Failed to refresh pipelines', e);
        }
        break;
      case 'datasource_update':
        try {
          const sources = await api.listDataSources();
          setDataSources(sources);
        } catch (e) {
          console.warn('[WS] Failed to refresh data sources', e);
        }
        break;
      case 'heartbeat':
        break;
      default:
        console.log('[WS] Unknown message type:', message.type);
    }
  }, [setMetrics, setPipelines, setDataSources]);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    const attempts = useAppStore.getState().wsReconnectAttempts;
    const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
    console.log(`[WS] Reconnecting in ${delay}ms...`);
    reconnectTimerRef.current = setTimeout(() => {
      incrementWsReconnect();
      // connect is defined below and referenced via closure
      connect();
    }, delay);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incrementWsReconnect]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
        setWsConnected(true);
        resetWsReconnect();
      };

      ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);
          handleMessage(message);
        } catch (e) {
          console.error('[WS] Failed to parse message', e);
        }
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected');
        setWsConnected(false);
        scheduleReconnect();
      };

      ws.onerror = (err) => {
        console.warn('[WS] Error', err);
        ws.close();
      };
    } catch (e) {
      console.warn('[WS] Connection failed', e);
      scheduleReconnect();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setWsConnected, resetWsReconnect]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connect]);
}
