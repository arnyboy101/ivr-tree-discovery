import { useEffect, useRef, useState, useCallback } from 'react';
import type { ServerMessage, ClientMessage } from '../types';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

export interface UseWebSocketReturn {
  status: ConnectionStatus;
  sendMessage: (data: ClientMessage) => void;
  onMessage: (handler: (msg: ServerMessage) => void) => void;
}

export function useWebSocket(sessionId: string): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<((msg: ServerMessage) => void)[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${window.location.host}/ws/${sessionId}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      setStatus('connecting');

      ws.onopen = () => {
        if (!unmounted) setStatus('connected');
      };

      ws.onclose = () => {
        if (!unmounted) {
          setStatus('disconnected');
          // Auto-reconnect after 2s
          reconnectTimer.current = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        // onclose will fire after onerror
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as ServerMessage;
          for (const handler of handlersRef.current) {
            handler(data);
          }
        } catch {
          // ignore non-JSON
        }
      };
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId]);

  const sendMessage = useCallback((data: ClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const onMessage = useCallback((handler: (msg: ServerMessage) => void) => {
    handlersRef.current = [handler];
  }, []);

  return { status, sendMessage, onMessage };
}
