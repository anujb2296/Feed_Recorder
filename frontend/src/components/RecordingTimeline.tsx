import { useState } from "react";
import { ChevronDown, ChevronRight, Play, Film } from "lucide-react";
import { Recording, groupByDate, formatBytes, formatDuration } from "../hooks/useRecordings";

interface RecordingTimelineProps {
  recordings:        Recording[];
  selectedId:        number | null;
  onSelect:          (rec: Recording) => void;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function getLocalDateString(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDateHeader(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dateObj = new Date(y, m - 1, d);
  const todayStr = getLocalDateString(new Date());
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = getLocalDateString(yesterday);

  if (dateStr === todayStr) return `Today — ${dateObj.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}`;
  if (dateStr === yesterdayStr) return `Yesterday — ${dateObj.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}`;
  return dateObj.toLocaleDateString([], { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

export default function RecordingTimeline({
  recordings, selectedId, onSelect,
}: RecordingTimelineProps) {
  const [openDays, setOpenDays] = useState<Set<string>>(new Set());
  const grouped  = groupByDate(recordings);
  const dates    = Object.keys(grouped).sort().reverse();  // newest first

  const toggleDay = (d: string) => {
    setOpenDays(prev => {
      const next = new Set(prev);
      next.has(d) ? next.delete(d) : next.add(d);
      return next;
    });
  };

  // Auto-open today on first render
  const todayStr = getLocalDateString(new Date());
  if (dates.includes(todayStr) && openDays.size === 0) {
    setOpenDays(new Set([todayStr]));
  }

  if (dates.length === 0) {
    return (
      <div className="empty-state">
        <Film size={48} />
        <div style={{ fontSize: 15, fontWeight: 600 }}>No recordings found</div>
        <div style={{ fontSize: 13 }}>Recordings will appear here as they are captured.</div>
      </div>
    );
  }

  return (
    <div className="timeline-container">
      {dates.map(date => {
        const recs    = grouped[date];
        const isOpen  = openDays.has(date);
        const totalSz = recs.reduce((s, r) => s + (r.file_size_bytes || 0), 0);

        return (
          <div key={date} className="timeline-day">
            <div className="timeline-day-header" onClick={() => toggleDay(date)}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                {isOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                <span className="timeline-day-date">{formatDateHeader(date)}</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {recs.length} segment{recs.length !== 1 ? "s" : ""} · {formatBytes(totalSz)}
              </div>
            </div>

            {isOpen && (
              <div className="timeline-segments">
                {recs.map(rec => (
                  <div
                    key={rec.id}
                    className={`segment-row${selectedId === rec.id ? " playing" : ""}`}
                    onClick={() => onSelect(rec)}
                  >
                    <Play size={13} style={{ color: selectedId === rec.id ? "var(--accent)" : "var(--text-muted)", flexShrink: 0 }} />
                    <span className="segment-time">
                      {formatTime(rec.start_time)}
                      {rec.end_time ? ` – ${formatTime(rec.end_time)}` : ""}
                    </span>
                    <span className="segment-cam-badge">{rec.camera_id}</span>
                    <span className="segment-duration">{formatDuration(rec.duration_seconds)}</span>
                    <span className="segment-size">{formatBytes(rec.file_size_bytes)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
