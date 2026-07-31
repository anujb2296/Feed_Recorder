import { useRef, useEffect } from "react";

interface VideoPlayerProps {
  recordingId: number | null;
  cameraName?: string;
}

export default function VideoPlayer({ recordingId, cameraName }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current && recordingId !== null) {
      videoRef.current.src = `/api/recordings/${recordingId}/stream`;
      videoRef.current.load();
      videoRef.current.play().catch(() => {});
    }
  }, [recordingId]);

  if (recordingId === null) {
    return (
      <div className="video-player-container" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", color: "var(--text-muted)" }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>▶</div>
          <div style={{ fontSize: 13 }}>Select a recording to play</div>
        </div>
      </div>
    );
  }

  return (
    <div className="video-player-container">
      <video
        ref={videoRef}
        controls
        style={{ width: "100%", height: "100%", objectFit: "contain", background: "#000" }}
        title={cameraName}
      />
    </div>
  );
}
