/**
 * useWebRTC.ts — WHEP-based WebRTC hook for go2rtc live streams.
 *
 * Protocol: WHEP (WebRTC-HTTP Egress Protocol)
 *   POST http://<server>:1984/api/whep?dst=<cameraId>
 *   Body: SDP offer (text/plain)
 *   Response: SDP answer (text/plain)
 *
 * No STUN/TURN needed — LAN-only, ICE negotiation uses link-local candidates.
 * Auto-retries with exponential backoff on connection failure.
 */
import { useEffect, useRef, useState, useCallback } from "react";

export type WebRTCStatus = "connecting" | "live" | "reconnecting" | "offline";

interface UseWebRTCOptions {
  cameraId: string;
  go2rtcUrl?: string;          // defaults to same host, port 1984
  enabled?: boolean;
}

interface UseWebRTCResult {
  videoRef: React.RefObject<HTMLVideoElement>;
  status: WebRTCStatus;
  latencyMs: number | null;    // rough wall-clock latency estimate (ms)
  retry: () => void;
}

const DEFAULT_GO2RTC_PORT = 1984;
const INITIAL_RETRY_MS    = 3_000;
const MAX_RETRY_MS        = 30_000;

function getGo2rtcUrl(): string {
  // Use relative URL so all requests go to port 8000 (FastAPI proxy)
  return window.location.origin;
}

export function useWebRTC({
  cameraId,
  go2rtcUrl,
  enabled = true,
}: UseWebRTCOptions): UseWebRTCResult {
  const videoRef  = useRef<HTMLVideoElement>(null);
  const pcRef     = useRef<RTCPeerConnection | null>(null);
  const retryRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryMs   = useRef(INITIAL_RETRY_MS);
  const mountedRef = useRef(true);

  const [status,    setStatus]    = useState<WebRTCStatus>("connecting");
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  const baseUrl = go2rtcUrl ?? getGo2rtcUrl();

  const cleanup = useCallback(() => {
    if (retryRef.current) clearTimeout(retryRef.current);
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const connect = useCallback(async () => {
    if (!mountedRef.current || !enabled) return;
    cleanup();
    setStatus("connecting");

    const requestStart = Date.now();

    try {
      const pc = new RTCPeerConnection({
        iceServers: [],                 // LAN-only — no STUN needed
        iceTransportPolicy: "all",
      });
      pcRef.current = pc;

      // We only want to receive — add recvonly transceivers
      pc.addTransceiver("video", { direction: "recvonly" });
      pc.addTransceiver("audio", { direction: "recvonly" });

      // Attach the incoming stream to the video element on first track
      pc.ontrack = (event) => {
        if (videoRef.current && event.streams[0]) {
          videoRef.current.srcObject = event.streams[0];
          videoRef.current.play().catch(() => {
            // Autoplay was blocked; mute and try again
            if (videoRef.current) {
              videoRef.current.muted = true;
              videoRef.current.play().catch(() => {});
            }
          });
          // Rough latency: time from WHEP request to first track event
          setLatencyMs(Date.now() - requestStart);
          setStatus("live");
          retryMs.current = INITIAL_RETRY_MS;  // reset backoff on success
        }
      };

      pc.oniceconnectionstatechange = () => {
        const state = pc.iceConnectionState;
        if (state === "failed" || state === "disconnected") {
          scheduleRetry();
        } else if (state === "closed") {
          if (mountedRef.current) setStatus("offline");
        }
      };

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "failed") scheduleRetry();
      };

      // Create SDP offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // WHEP: POST offer to go2rtc
      const whepUrl = `${baseUrl}/api/whep?dst=${encodeURIComponent(cameraId)}`;
      const resp = await fetch(whepUrl, {
        method:  "POST",
        headers: { "Content-Type": "application/sdp" },
        body:    offer.sdp,
      });

      if (!resp.ok) {
        throw new Error(`WHEP error: ${resp.status} ${resp.statusText}`);
      }

      const answerSdp = await resp.text();
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

    } catch (err) {
      console.warn(`[${cameraId}] WebRTC connect failed:`, err);
      if (mountedRef.current) scheduleRetry();
    }
  }, [cameraId, baseUrl, enabled, cleanup]);  // eslint-disable-line

  const scheduleRetry = useCallback(() => {
    if (!mountedRef.current) return;
    cleanup();
    setStatus("reconnecting");
    const delay = retryMs.current;
    retryMs.current = Math.min(retryMs.current * 2, MAX_RETRY_MS);
    retryRef.current = setTimeout(() => {
      if (mountedRef.current) connect();
    }, delay);
  }, [cleanup, connect]);

  // Public retry (resets backoff)
  const retry = useCallback(() => {
    retryMs.current = INITIAL_RETRY_MS;
    connect();
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) connect();
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [enabled, connect, cleanup]);

  return { videoRef, status, latencyMs, retry };
}
