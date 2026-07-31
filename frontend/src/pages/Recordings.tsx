import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { useRecordings, Recording } from "../hooks/useRecordings";
import RecordingTimeline from "../components/RecordingTimeline";
import VideoPlayer from "../components/VideoPlayer";

const DURATION_OPTIONS = [1, 2, 3, 5, 10, 15, 20, 30];
const CAMERA_OPTIONS = [
  { value: "",     label: "All Cameras" },
  { value: "cam1", label: "Camera 1" },
  { value: "cam2", label: "Camera 2" },
];

export default function Recordings() {
  const [days,         setDays]         = useState(7);
  const [cameraFilter, setCameraFilter] = useState("");
  const [selected,     setSelected]     = useState<Recording | null>(null);

  const { recordings, loading, error, refresh } = useRecordings({
    days,
    cameraId: cameraFilter || undefined,
  });

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Recordings</h1>
        <p className="page-subtitle">
          Browse and play back recorded footage.
          The duration selector only controls what's displayed — nothing is ever auto-deleted.
        </p>
      </div>

      <div className="page-body" style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 24, alignItems: "start" }}>
        {/* ── Left: filters + timeline ── */}
        <div>
          {/* Duration selector */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 8 }}>
              Show last
            </div>
            <div className="duration-selector">
              {DURATION_OPTIONS.map(d => (
                <button
                  key={d}
                  className={`duration-btn${days === d ? " active" : ""}`}
                  onClick={() => setDays(d)}
                >
                  {d} {d === 1 ? "day" : "days"}
                </button>
              ))}
            </div>
          </div>

          {/* Camera filter */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 8 }}>
              Camera
            </div>
            <div className="camera-filter">
              {CAMERA_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  className={`duration-btn${cameraFilter === opt.value ? " active" : ""}`}
                  onClick={() => setCameraFilter(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Controls */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {loading ? "Loading..." : error ? `Error: ${error}` : `${recordings.length} segment${recordings.length !== 1 ? "s" : ""} found`}
            </div>
            <button className="btn btn-ghost btn-sm" onClick={refresh} disabled={loading}>
              <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
              Refresh
            </button>
          </div>

          {/* Timeline */}
          <RecordingTimeline
            recordings={recordings}
            selectedId={selected?.id ?? null}
            onSelect={setSelected}
          />
        </div>

        {/* ── Right: video player (sticky) ── */}
        <div>
          <VideoPlayer
            recordingId={selected?.id ?? null}
            cameraName={selected?.camera_name}
          />
          {selected && (
            <div style={{ marginTop: 12, padding: "12px 0", borderTop: "1px solid var(--border)" }}>
              <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
                <strong style={{ color: "var(--text-primary)" }}>{selected.camera_name}</strong>
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                {new Date(selected.start_time).toLocaleString()}
                {selected.end_time && ` → ${new Date(selected.end_time).toLocaleTimeString()}`}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
