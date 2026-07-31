import { CameraOff, RefreshCw } from "lucide-react";
import { useWebRTC, WebRTCStatus } from "../hooks/useWebRTC";

interface CameraTileProps {
  cameraId:   string;
  cameraName: string;
}

function StatusBadge({ status }: { status: WebRTCStatus }) {
  if (status === "live")
    return (
      <span className="badge badge-live">
        <span className="pulse" /> Live
      </span>
    );
  if (status === "connecting" || status === "reconnecting")
    return (
      <span className="badge badge-reconnecting">
        <RefreshCw size={10} style={{ animation: "spin 1s linear infinite" }} />
        {status === "connecting" ? "Connecting" : "Reconnecting"}
      </span>
    );
  return <span className="badge badge-offline">Offline</span>;
}

export default function CameraTile({ cameraId, cameraName }: CameraTileProps) {
  const { videoRef, status, latencyMs, retry } = useWebRTC({ cameraId });

  const showVideo = status === "live";

  return (
    <div className="camera-tile">
      {/* Video element — always rendered so the ref is stable */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{ display: showVideo ? "block" : "none" }}
      />

      {/* Placeholder when not live */}
      {!showVideo && (
        <div className="camera-tile-placeholder">
          <CameraOff size={40} />
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            {status === "connecting"    && "Connecting to camera..."}
            {status === "reconnecting" && "Reconnecting..."}
            {status === "offline"      && "Camera offline"}
          </div>
          {status === "offline" && (
            <button className="btn btn-ghost btn-sm" onClick={retry}>
              <RefreshCw size={13} /> Retry
            </button>
          )}
        </div>
      )}

      {/* Top-right: status + latency */}
      <div className="camera-tile-info">
        <StatusBadge status={status} />
        {latencyMs !== null && status === "live" && (
          <span className="latency-badge">{latencyMs} ms</span>
        )}
      </div>

      {/* Bottom overlay: camera name */}
      <div className="camera-tile-overlay">
        <span className="camera-tile-name">{cameraName}</span>
      </div>
    </div>
  );
}
