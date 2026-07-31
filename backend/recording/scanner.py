"""
scanner.py — Background task that scans the recordings directory
             and keeps the database in sync with what's on disk.

Runs every 60 seconds. For each .mp4 file found:
 - If not in DB → insert as 'completed' (use ffprobe for metadata)
 - If in DB as 'recording' and the file hasn't grown in 2 checks → mark 'completed'
 - If the file is currently the newest for a camera → keep as 'recording'
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from database import get_db, Recording

logger = logging.getLogger(__name__)

SCAN_INTERVAL = 60  # seconds


async def ffprobe_duration(file_path: str) -> Optional[float]:
    """Get duration of an MP4 file in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        data = json.loads(stdout)
        return float(data["format"]["duration"])
    except Exception:
        return None


def _parse_start_time(file_path: Path) -> Optional[datetime]:
    """
    Extract start time from filename.
    Expected filename pattern: HH-MM-SS.mp4
    Parent dir pattern: YYYY-MM-DD
    """
    try:
        time_str = file_path.stem          # e.g. "14-30-00"
        date_str = file_path.parent.name   # e.g. "2026-07-31"
        return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H-%M-%S")
    except Exception:
        return None


class DirectoryScanner:
    def __init__(self, storage_path: str, cameras: list[dict]):
        self.storage_path = storage_path
        self.cameras = cameras
        self._task: Optional[asyncio.Task] = None
        # Track file sizes across scans to detect "still being written"
        self._prev_sizes: dict[str, int] = {}

    def _list_mp4s(self, camera_id: str) -> list[Path]:
        """Recursively list all .mp4 files under /<storage>/<camera_id>/"""
        base = Path(self.storage_path) / camera_id
        if not base.exists():
            return []
        return sorted(base.rglob("*.mp4"))

    async def _sync_camera(self, camera: dict) -> None:
        camera_id   = camera["id"]
        camera_name = camera["name"]
        mp4s        = self._list_mp4s(camera_id)

        if not mp4s:
            return

        # The most recently modified file is likely still being written
        newest_path = max(mp4s, key=lambda p: p.stat().st_mtime)

        with get_db() as db:
            for mp4 in mp4s:
                path_str = str(mp4)
                existing = db.query(Recording).filter_by(file_path=path_str).first()
                is_newest = (mp4 == newest_path)

                if existing is None:
                    # New file found on disk — insert it
                    start_time = _parse_start_time(mp4)
                    if start_time is None:
                        continue  # can't parse, skip
                    size = mp4.stat().st_size
                    duration = None if is_newest else await ffprobe_duration(path_str)
                    rec = Recording(
                        camera_id        = camera_id,
                        camera_name      = camera_name,
                        file_path        = path_str,
                        start_time       = start_time,
                        end_time         = None,
                        duration_seconds = duration,
                        file_size_bytes  = size,
                        status           = "recording" if is_newest else "completed",
                    )
                    db.add(rec)
                    logger.info(
                        f"[scanner] Added {mp4.name} → "
                        f"{'recording' if is_newest else 'completed'}"
                    )

                elif existing.status == "recording" and not is_newest:
                    # Was being recorded, now another file is newer → finalize it
                    size     = mp4.stat().st_size
                    duration = await ffprobe_duration(path_str)
                    existing.status           = "completed"
                    existing.file_size_bytes  = size
                    existing.duration_seconds = duration
                    if duration and existing.start_time:
                        from datetime import timedelta
                        existing.end_time = (
                            existing.start_time + timedelta(seconds=duration)
                        )
                    logger.info(f"[scanner] Finalized {mp4.name}")

                elif existing.status == "completed":
                    # Update size in case it changed (shouldn't, but keep in sync)
                    current_size = mp4.stat().st_size
                    if existing.file_size_bytes != current_size:
                        existing.file_size_bytes = current_size

    async def _scan_loop(self) -> None:
        while True:
            await asyncio.sleep(SCAN_INTERVAL)
            try:
                for cam in self.cameras:
                    await self._sync_camera(cam)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[scanner] Error during scan: {e}", exc_info=True)

    async def start(self) -> None:
        # Run once immediately on startup, then enter loop
        try:
            for cam in self.cameras:
                await self._sync_camera(cam)
        except Exception as e:
            logger.error(f"[scanner] Initial scan error: {e}", exc_info=True)

        self._task = asyncio.create_task(self._scan_loop(), name="dir-scanner")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
