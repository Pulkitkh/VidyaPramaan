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

/** Subscribes to the server's event stream; returns connection state and the latest events.
 *  The connection uses a 60-second ticket fetched with the session header, so the session token is
 *  never placed in a URL. On disconnect it fetches a fresh ticket and reconnects. */
export function useLiveEvents(onEvent?: (e: LiveEvent) => void) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const cb = useRef(onEvent);
  cb.current = onEvent;
  useEffect(() => {
    if (!getToken() || typeof EventSource === "undefined") return;
    let es: EventSource | null = null;
    let stopped = false;
    let retry: number | undefined;
    const connect = async () => {
      try {
        const { ticket } = await api<{ ticket: string }>("/api/events/ticket", { method: "POST" });
        if (stopped) return;
        es = new EventSource(`/api/events?ticket=${encodeURIComponent(ticket)}`);
        es.addEventListener("hello", () => setConnected(true));
        es.onmessage = (m) => {
          try {
            const ev = JSON.parse(m.data) as LiveEvent;
            setEvents((prev) => [ev, ...prev].slice(0, 20));
            cb.current?.(ev);
          } catch { /* ignore malformed */ }
        };
        es.onerror = () => {
          setConnected(false);
          es?.close();
          if (!stopped) retry = window.setTimeout(connect, 3000);
        };
      } catch {
        if (!stopped) retry = window.setTimeout(connect, 5000);
      }
    };
    connect();
    return () => { stopped = true; window.clearTimeout(retry); es?.close(); };
  }, []);
  return { connected, events };
}
