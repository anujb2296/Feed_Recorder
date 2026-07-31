"""
reconciler.py — On startup, reconcile database state with actual disk contents.

After a crash or unexpected shutdown:
 - Recordings with status='recording' may have a partial but valid MP4 on disk.
 - This module inspects each such file, gets its real duration via ffprobe,
   and marks it 'completed'. If the file is missing, it's marked as a 'gap'.

Run once during the FastAPI lifespan startup event, before workers start.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from database import get_db, Recording

logger = logging.getLogger(__name__)


async def _ffprobe_info(file_path: str) -> Optional[dict]:
    """Get format info (duration, size) from an MP4 file using ffprobe."""
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
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        data = json.loads(stdout)
        fmt = data.get("format", {})
        return {
            "duration": float(fmt.get("duration", 0)),
            "size":     int(fmt.get("size", 0)),
        }
    except asyncio.TimeoutError:
        logger.warning(f"[reconciler] ffprobe timed out for: {file_path}")
        return None
    except Exception as e:
        logger.warning(f"[reconciler] ffprobe error for {file_path}: {e}")
        return None


async def reconcile_on_startup() -> None:
    """
    Find all DB rows with status='recording', check the file on disk,
    and update their status to 'completed' or 'gap' accordingly.
    """
    with get_db() as db:
        in_progress_rows = (
            db.query(Recording.id, Recording.file_path, Recording.start_time)
            .filter(Recording.status == "recording")
            .all()
        )

    if not in_progress_rows:
        logger.info("[reconciler] No in-progress recordings to reconcile.")
        return

    logger.info(
        f"[reconciler] Found {len(in_progress_rows)} recording(s) to reconcile "
        "(likely from a previous crash or shutdown)."
    )

    for rec_id, file_path, start_time in in_progress_rows:
        path = Path(file_path)

        if not path.exists():
            # File missing → log as gap
            with get_db() as db:
                r = db.query(Recording).get(rec_id)
                if r:
                    r.status = "gap"
            logger.warning(
                f"[reconciler] File missing → gap: {file_path}"
            )
            continue

        info = await _ffprobe_info(file_path)
        if info is None:
            # Can't probe → leave as 'recording' (scanner will handle it later)
            logger.warning(
                f"[reconciler] Could not probe file, leaving as-is: {file_path}"
            )
            continue

        duration = info["duration"]
        size     = info["size"]
        end_time = (
            start_time + timedelta(seconds=duration)
            if start_time and duration > 0
            else None
        )

        with get_db() as db:
            r = db.query(Recording).get(rec_id)
            if r:
                r.status           = "completed"
                r.duration_seconds = duration
                r.file_size_bytes  = size
                r.end_time         = end_time

        logger.info(
            f"[reconciler] Reconciled: {path.name} "
            f"({duration:.1f}s, {size / 1_048_576:.1f} MB)"
        )

    logger.info("[reconciler] Reconciliation complete.")
