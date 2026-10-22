import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken } from "./api";

export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}

export interface LiveEvent { type: string; [k: string]: unknown }

/** Subscribes to the server's event stream; returns connection state and the latest events. */
export function useLiveEvents(onEvent?: (e: LiveEvent) => void) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const cb = useRef(onEvent);
  cb.current = onEvent;
  useEffect(() => {
    const token = getToken();
    if (!token || typeof EventSource === "undefined") return;
    const es = new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
    es.addEventListener("hello", () => setConnected(true));
    es.onmessage = (m) => {
      try {
        const ev = JSON.parse(m.data) as LiveEvent;
        setEvents((prev) => [ev, ...prev].slice(0, 20));
        cb.current?.(ev);
      } catch { /* ignore malformed */ }
    };
    es.onerror = () => setConnected(false);
    return () => es.close();
  }, []);
  return { connected, events };
}
