"use client";

import { useEffect, useRef, useCallback, useState } from "react";

interface LiveUpdate {
  type: "shipment_updated" | "prediction_updated" | "scrape_completed" | "stats_updated";
  shipment_id: string;
  tracking_number: string;
  carrier_slug: string;
  status?: string;
  user_id?: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

interface UseEventStreamOptions {
  onUpdate?: (event: LiveUpdate) => void;
  onStatusChange?: (shipmentId: string, newStatus: string) => void;
  enabled?: boolean;
}

export function useEventStream(options: UseEventStreamOptions = {}) {
  const { onUpdate, onStatusChange, enabled = true } = options;
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<LiveUpdate | null>(null);
  const [updateCount, setUpdateCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!enabled || eventSourceRef.current) return;

    const es = new EventSource("/api/events");

    es.addEventListener("connected", () => {
      setConnected(true);
    });

    es.addEventListener("update", (e) => {
      try {
        const event: LiveUpdate = JSON.parse(e.data);
        setLastUpdate(event);
        setUpdateCount((c) => c + 1);
        onUpdate?.(event);
        if (event.status && event.shipment_id) {
          onStatusChange?.(event.shipment_id, event.status);
        }
      } catch {}
    });

    es.addEventListener("heartbeat", () => {});

    es.onerror = () => {
      setConnected(false);
      es.close();
      eventSourceRef.current = null;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = setTimeout(connect, 5000);
    };

    eventSourceRef.current = es;
  }, [enabled, onUpdate, onStatusChange]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      setConnected(false);
    };
  }, [connect]);

  return { connected, lastUpdate, updateCount };
}
