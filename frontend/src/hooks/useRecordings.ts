/**
 * useRecordings.ts — Data-fetching hook for recording segments.
 */
import { useEffect, useState, useCallback } from "react";

export interface Recording {
  id:               number;
  camera_id:        string;
  camera_name:      string;
  file_path:        string;
  start_time:       string;
  end_time:         string | null;
  duration_seconds: number | null;
  file_size_bytes:  number | null;
  status:           "recording" | "completed" | "gap";
}

interface UseRecordingsOptions {
  days?:      number;
  cameraId?:  string;
  date?:      string;
}

export function useRecordings({ days, cameraId, date }: UseRecordingsOptions = {}) {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (days)     params.set("days",      String(days));
    if (cameraId) params.set("camera_id", cameraId);
    if (date)     params.set("date",      date);

    try {
      const resp = await fetch(`/api/recordings?${params}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setRecordings(await resp.json());
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [days, cameraId, date]);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { recordings, loading, error, refresh: fetch_ };
}

/** Group recordings by date string (YYYY-MM-DD). */
export function groupByDate(recordings: Recording[]): Record<string, Recording[]> {
  const groups: Record<string, Recording[]> = {};
  for (const r of recordings) {
    const d = r.start_time.slice(0, 10);
    if (!groups[d]) groups[d] = [];
    groups[d].push(r);
  }
  return groups;
}

/** Format file size in human-readable form. */
export function formatBytes(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024)              return `${bytes} B`;
  if (bytes < 1024 * 1024)      return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3)        return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

/** Format duration seconds as HH:MM:SS or MM:SS. */
export function formatDuration(secs: number | null): string {
  if (secs === null) return "—";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (h > 0) return `${h}h ${m.toString().padStart(2,"0")}m`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
