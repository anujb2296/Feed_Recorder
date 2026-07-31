"""
worker.py — Per-camera ffmpeg recording worker.

Each worker:
 - Ensures date-stamped subdirectories exist under /<storage>/<camera_id>/<YYYY-MM-DD>/
 - Runs ffmpeg in segment mode (-c copy, no re-encode)
 - Auto-restarts on crash/disconnect with exponential backoff
 - Registers recording state in the database
"""
import asyncio
import logging
import os
import subprocess
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Backoff settings
INITIAL_RETRY_DELAY = 5      # seconds
MAX_RETRY_DELAY     = 60     # seconds
MIN_RUNTIME_FOR_RESET = 30   # if ffmpeg ran > this many seconds, reset backoff


class RecordingWorker:
    def __init__(
        self,
        camera_id: str,
        camera_name: str,
        rtsp_url: str,
        storage_path: str,
        segment_seconds: int,
        on_status_change: Optional[Callable[[str, str], None]] = None,
    ):
        self.camera_id      = camera_id
        self.camera_name    = camera_name
        self.rtsp_url       = rtsp_url
        self.storage_path   = storage_path
        self.segment_seconds = segment_seconds
        self.on_status_change = on_status_change

        self._process: Optional[asyncio.subprocess.Process] = None
        self._running   = False
        self._status    = "offline"
        self._task: Optional[asyncio.Task] = None
        self.codec_info: Optional[dict] = None   # set by camera probe at startup

    # ─── Status ─────────────────────────────────────────────────────────────

    @property
    def status(self) -> str:
        return self._status

    def _set_status(self, status: str) -> None:
        if self._status != status:
            self._status = status
            logger.info(f"[{self.camera_id}] status → {status}")
            if self.on_status_change:
                self.on_status_change(self.camera_id, status)

    # ─── Directory helpers ───────────────────────────────────────────────────

    def _camera_base(self) -> Path:
        return Path(self.storage_path) / self.camera_id

    def _ensure_date_dirs(self) -> None:
        """Pre-create today and tomorrow directories so ffmpeg strftime works."""
        today    = datetime.now()
        tomorrow = today + timedelta(days=1)
        for dt in (today, tomorrow):
            d = self._camera_base() / dt.strftime("%Y-%m-%d")
            d.mkdir(parents=True, exist_ok=True)

    # ─── ffmpeg command ──────────────────────────────────────────────────────

    def _ffmpeg_cmd(self) -> list[str]:
        """Build the ffmpeg command for continuous segmented recording."""
        out_pattern = str(
            self._camera_base() / "%Y-%m-%d" / "%H-%M-%S.mp4"
        )
        return [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-use_wallclock_as_timestamps", "1",
            "-i", self.rtsp_url,
            "-c", "copy",          # NO RE-ENCODE — stream copy only
            "-map", "0",
            "-f", "segment",
            "-segment_time",   str(self.segment_seconds),
            "-segment_format", "mp4",
            "-reset_timestamps", "1",
            "-strftime", "1",
            "-avoid_negative_ts", "1",
            out_pattern,
            "-y",
            "-loglevel", "warning",
        ]

    # ─── Codec probe ─────────────────────────────────────────────────────────

    async def probe_camera(self) -> dict:
        """
        Probe the RTSP stream with ffprobe to get codec and keyframe interval.
        Logs a WARNING if codec is H.265/HEVC or if keyframe interval > 1s.
        Returns a dict with codec info (or empty dict on failure).
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-rtsp_transport", "tcp",
            "-print_format", "json",
            "-show_streams",
            "-read_intervals", "%+3",   # probe first 3 seconds only
            self.rtsp_url,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            data = json.loads(stdout)
            video = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                None,
            )
            if not video:
                logger.warning(f"[{self.camera_id}] ffprobe: no video stream found")
                return {}

            codec = video.get("codec_name", "unknown").lower()
            fps_str = video.get("avg_frame_rate", "0/1")
            try:
                num, den = map(int, fps_str.split("/"))
                fps = num / den if den else 0
            except Exception:
                fps = 0

            # keyframe interval from tags (not always available)
            keyint = None
            tags = video.get("tags", {})
            if "GOPSIZE" in tags:
                try:
                    keyint = float(tags["GOPSIZE"]) / fps if fps else None
                except Exception:
                    pass

            info = {
                "codec": codec,
                "fps": round(fps, 2),
                "width": video.get("width"),
                "height": video.get("height"),
                "keyframe_interval_sec": keyint,
            }
            self.codec_info = info

            # ── Warnings ─────────────────────────────────────────────────────
            if codec in ("hevc", "h265"):
                logger.warning(
                    f"[{self.camera_id}] ⚠️  CAMERA USES H.265/HEVC — "
                    "browsers cannot decode H.265 via WebRTC natively! "
                    "Live view will NOT work. Configure the camera to output H.264, "
                    "or contact us to add a transcoding step."
                )
            elif codec == "h264":
                logger.info(f"[{self.camera_id}] ✅ Codec: H.264  FPS: {fps}")
            else:
                logger.warning(f"[{self.camera_id}] ⚠️  Unknown codec: {codec}")

            if keyint is not None and keyint > 1.5:
                logger.warning(
                    f"[{self.camera_id}] ⚠️  Keyframe interval is ~{keyint:.1f}s — "
                    "for <150ms WebRTC latency, set it to ≤1s on the camera."
                )
            elif keyint is None:
                logger.info(
                    f"[{self.camera_id}] Keyframe interval not reported by camera. "
                    "If live view latency is high (>2s), set GOP to 1s on the camera."
                )

            return info

        except asyncio.TimeoutError:
            logger.warning(f"[{self.camera_id}] ffprobe timed out — camera may be offline")
            return {}
        except Exception as e:
            logger.warning(f"[{self.camera_id}] ffprobe error: {e}")
            return {}

    # ─── Run loop ────────────────────────────────────────────────────────────

    async def _run_once(self) -> int:
        """Start ffmpeg, wait for it to exit. Returns exit code."""
        self._ensure_date_dirs()
        cmd = self._ffmpeg_cmd()
        logger.info(f"[{self.camera_id}] Starting ffmpeg")
        self._set_status("recording")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            start_time = asyncio.get_event_loop().time()

            # Read stderr asynchronously (non-blocking), log in chunks
            stderr_lines = []
            async for line in self._process.stderr:
                decoded = line.decode(errors="replace").strip()
                if decoded:
                    stderr_lines.append(decoded)
                    if len(stderr_lines) <= 5:          # log first few lines
                        logger.debug(f"[{self.camera_id}] ffmpeg: {decoded}")

            await self._process.wait()
            runtime = asyncio.get_event_loop().time() - start_time
            exit_code = self._process.returncode
            if exit_code != 0 and stderr_lines:
                logger.warning(
                    f"[{self.camera_id}] ffmpeg exited {exit_code} "
                    f"after {runtime:.1f}s. Last error: {stderr_lines[-1]}"
                )
            return exit_code, runtime

        except Exception as e:
            logger.error(f"[{self.camera_id}] ffmpeg launch error: {e}")
            return -1, 0
        finally:
            self._process = None

    async def run(self) -> None:
        """Supervisor loop: run ffmpeg, restart with exponential backoff."""
        self._running = True
        retry_delay = INITIAL_RETRY_DELAY

        while self._running:
            exit_code, runtime = await self._run_once()

            if not self._running:
                break

            # Reset backoff if ffmpeg ran long enough (camera was fine, transient drop)
            if runtime >= MIN_RUNTIME_FOR_RESET:
                retry_delay = INITIAL_RETRY_DELAY

            self._set_status("reconnecting")
            logger.info(
                f"[{self.camera_id}] Reconnecting in {retry_delay}s "
                f"(exit={exit_code}, runtime={runtime:.1f}s)"
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)

        self._set_status("offline")

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self.run(), name=f"recording-{self.camera_id}"
            )

    async def stop(self) -> None:
        """Gracefully stop ffmpeg and the supervisor loop."""
        self._running = False
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                self._process.kill()
            except ProcessLookupError:
                pass
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._set_status("offline")
