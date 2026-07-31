import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import CameraTile from "../components/CameraTile";

interface CameraInfo {
  id:     string;
  name:   string;
  status: string;
  codec:  string | null;
  fps:    number | null;
  width:  number | null;
  height: number | null;
  keyframe_interval_sec: number | null;
}

export default function Live() {
  const [cameras,      setCameras]      = useState<CameraInfo[]>([]);
  const [showCodecInfo, setShowCodecInfo] = useState(false);

  useEffect(() => {
    fetch("/api/cameras")
      .then(r => r.json())
      .then(setCameras)
      .catch(console.error);

    // Poll camera status every 5 seconds
    const iv = setInterval(() => {
      fetch("/api/cameras")
        .then(r => r.json())
        .then(setCameras)
        .catch(() => {});
    }, 5000);
    return () => clearInterval(iv);
  }, []);

  return (
    <>
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h1 className="page-title">Live View</h1>
            <p className="page-subtitle">
              WebRTC streams via go2rtc · Target latency: 50–150 ms
            </p>
          </div>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setShowCodecInfo(v => !v)}
            style={{ marginBottom: 20 }}
          >
            <Info size={14} /> Camera Info
          </button>
        </div>
      </div>

      <div className="page-body">
        {/* Camera info panel (debug) */}
        {showCodecInfo && cameras.length > 0 && (
          <div className="card mb-4" style={{ marginBottom: 20 }}>
            <div className="card-title">Camera Codec Info</div>
            <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ color: "var(--text-muted)" }}>
                  {["Camera","Codec","FPS","Resolution","Keyframe Interval","Status"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cameras.map(cam => (
                  <tr key={cam.id}>
                    <td style={{ padding: "8px 8px", color: "var(--text-primary)" }}>{cam.name}</td>
                    <td style={{ padding: "8px 8px" }}>
                      <span style={{
                        color: cam.codec === "h264" ? "var(--success)"
                               : cam.codec ? "var(--danger)" : "var(--text-muted)"
                      }}>
                        {cam.codec?.toUpperCase() ?? "—"}
                        {cam.codec && cam.codec !== "h264" && " ⚠️"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 8px", color: "var(--text-secondary)" }}>{cam.fps ?? "—"}</td>
                    <td style={{ padding: "8px 8px", color: "var(--text-secondary)" }}>
                      {cam.width && cam.height ? `${cam.width}×${cam.height}` : "—"}
                    </td>
                    <td style={{ padding: "8px 8px" }}>
                      {cam.keyframe_interval_sec !== null ? (
                        <span style={{ color: (cam.keyframe_interval_sec ?? 0) > 1.5 ? "var(--warning)" : "var(--success)" }}>
                          ~{cam.keyframe_interval_sec?.toFixed(1)}s
                          {(cam.keyframe_interval_sec ?? 0) > 1.5 && " ⚠️ set to ≤1s"}
                        </span>
                      ) : <span style={{ color: "var(--text-muted)" }}>—</span>}
                    </td>
                    <td style={{ padding: "8px 8px" }}>
                      <span className={`badge ${
                        cam.status === "recording" ? "badge-live"
                        : cam.status === "reconnecting" ? "badge-reconnecting"
                        : "badge-offline"
                      }`}>
                        {cam.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Camera grid */}
        <div className="camera-grid">
          {cameras.length === 0
            ? [{ id: "cam1", name: "Camera 1" }, { id: "cam2", name: "Camera 2" }].map(c => (
                <CameraTile key={c.id} cameraId={c.id} cameraName={c.name} />
              ))
            : cameras.map(cam => (
                <CameraTile key={cam.id} cameraId={cam.id} cameraName={cam.name} />
              ))
          }
        </div>

        {/* Latency note */}
        <div style={{ marginTop: 16, fontSize: 12, color: "var(--text-muted)" }}>
          ⓘ  Latency shown is wall-clock time from WHEP request to first video frame.
          For sub-150ms latency, ensure the camera's keyframe interval is ≤ 1 second.
        </div>
      </div>
    </>
  );
}
