import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { API_BASE_URL } from '../api/client';

const WebSocketContext = createContext(null);

export function WebSocketProvider({ children }) {
  const { token, isAuthenticated } = useAuth();
  const [status, setStatus] = useState('disconnected'); // 'connecting' | 'connected' | 'disconnected'
  const [toasts, setToasts] = useState([]);
  const [lastEvent, setLastEvent] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const listenersRef = useRef(new Set());

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Add a toast notification
  const addToast = useCallback((toast) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 9);
    const newToast = {
      id,
      type: toast.type || 'info', // 'info' | 'success' | 'warning' | 'error'
      title: toast.title,
      message: toast.message,
      timestamp: new Date(),
    };

    setToasts((prev) => [newToast, ...prev].slice(0, 5)); // Keep max 5 toasts

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      removeToast(id);
    }, 5000);
  }, [removeToast]);

  const addToastRef = useRef(addToast);
  addToastRef.current = addToast;

  // Register event listener
  const subscribe = useCallback((callback) => {
    listenersRef.current.add(callback);
    return () => {
      listenersRef.current.delete(callback);
    };
  }, []);

  const connect = useCallback(() => {
    if (!token || !isAuthenticated) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setStatus('disconnected');
      return;
    }

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      setStatus('connecting');
      const wsUrl = API_BASE_URL.replace(/^http/, 'ws');
      const fullUrl = `${wsUrl}/ws/updates?token=${encodeURIComponent(token)}`;

      const socket = new WebSocket(fullUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setStatus('connected');
        console.log('[WebSocket] Connected successfully to backend updates.');
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setLastEvent(payload);

          // Dispatch to all registered subscriber callbacks
          listenersRef.current.forEach((cb) => {
            try {
              cb(payload);
            } catch (err) {
              console.error('[WebSocket] Error in subscriber callback:', err);
            }
          });

          // Generate meaningful notifications
          const ev = payload.event;
          const data = payload.data || {};

          if (ev === 'meeting.processed') {
            addToastRef.current({
              type: 'success',
              title: 'Meeting Processed',
              message: `Created ${data.action_items_created || 0} action items, ${data.decisions_created || 0} decisions.`,
            });
          } else if (ev === 'action_item.created') {
            addToastRef.current({
              type: 'info',
              title: 'New Action Item',
              message: `"${data.task || 'Action item'}" (Owner: ${data.owner || 'Unassigned'})`,
            });
          } else if (ev === 'action_item.updated') {
            addToastRef.current({
              type: 'info',
              title: 'Action Item Updated',
              message: `"${data.task || 'Action item'}" status: ${data.status || 'updated'}`,
            });
          } else if (ev === 'action_item.confirmed') {
            addToastRef.current({
              type: 'success',
              title: 'Action Item Confirmed',
              message: `Item #${data.id} confirmed and ready.`,
            });
          } else if (ev === 'action_item.deleted') {
            addToastRef.current({
              type: 'info',
              title: 'Duplicate Merged',
              message: `Duplicate item #${data.deleted_item_id} merged into primary.`,
            });
          } else if (ev === 'action_item.overdue') {
            addToastRef.current({
              type: 'warning',
              title: 'Overdue Task Alert',
              message: `"${data.task}" (Deadline: ${data.deadline || 'Past'}) is overdue!`,
            });
          } else if (ev === 'clarification.reminder') {
            addToastRef.current({
              type: 'warning',
              title: 'Clarification Reminder',
              message: `Action item #${data.action_item_id} has been awaiting clarification > 24 hours.`,
            });
          }
        } catch (e) {
          console.warn('[WebSocket] Error parsing incoming message:', e);
        }
      };

      socket.onerror = (err) => {
        console.warn('[WebSocket] Connection error:', err);
      };

      socket.onclose = (event) => {
        setStatus('disconnected');
        wsRef.current = null;
        if (isAuthenticated && token) {
          // Reconnect attempt after 3 seconds
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 3000);
        }
      };
    } catch (err) {
      console.error('[WebSocket] Setup exception:', err);
      setStatus('disconnected');
    }
  }, [token, isAuthenticated]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const value = {
    status,
    toasts,
    lastEvent,
    addToast,
    removeToast,
    subscribe,
  };

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
}
