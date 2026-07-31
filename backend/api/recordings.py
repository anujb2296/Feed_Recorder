"""
api/recordings.py — Endpoints for listing and streaming recordings.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db_dep, Recording

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.get("")
def list_recordings(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    days: Optional[int]      = Query(None, description="Only show last N days"),
    date: Optional[str]      = Query(None, description="Filter to a specific date YYYY-MM-DD"),
    db: Session              = Depends(get_db_dep),
):
    """
    List recording segments. Supports filtering by camera, date range,
    or a specific date. Ordered by start_time ascending.
    """
    q = db.query(Recording).filter(Recording.status != "gap")

    if camera_id:
        q = q.filter(Recording.camera_id == camera_id)

    if date:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            q = q.filter(
                Recording.start_time >= d,
                Recording.start_time < d + timedelta(days=1),
            )
        except ValueError:
            raise HTTPException(400, "date must be YYYY-MM-DD")

    elif days:
        since = datetime.now() - timedelta(days=days)
        q = q.filter(Recording.start_time >= since)

    rows = q.order_by(Recording.start_time.asc()).all()

    return [
        {
            "id":               r.id,
            "camera_id":        r.camera_id,
            "camera_name":      r.camera_name,
            "file_path":        r.file_path,
            "start_time":       r.start_time.isoformat() if r.start_time else None,
            "end_time":         r.end_time.isoformat() if r.end_time else None,
            "duration_seconds": r.duration_seconds,
            "file_size_bytes":  r.file_size_bytes,
            "status":           r.status,
        }
        for r in rows
    ]


@router.get("/gaps")
def list_gaps(
    camera_id: Optional[str] = Query(None),
    days: Optional[int]      = Query(7),
    db: Session              = Depends(get_db_dep),
):
    """List gap entries (time ranges where no recording was available)."""
    q = db.query(Recording).filter(Recording.status == "gap")
    if camera_id:
        q = q.filter(Recording.camera_id == camera_id)
    if days:
        since = datetime.now() - timedelta(days=days)
        q = q.filter(Recording.start_time >= since)
    rows = q.order_by(Recording.start_time.asc()).all()
    return [
        {
            "id":         r.id,
            "camera_id":  r.camera_id,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "end_time":   r.end_time.isoformat() if r.end_time else None,
        }
        for r in rows
    ]


@router.get("/{recording_id}/stream")
def stream_recording(
    recording_id: int,
    db: Session = Depends(get_db_dep),
):
    """
    Stream an MP4 recording file. FastAPI's FileResponse supports
    HTTP Range requests so the browser video player can seek.
    """
    rec = db.query(Recording).get(recording_id)
    if not rec:
        raise HTTPException(404, "Recording not found")

    path = Path(rec.file_path)
    if not path.exists():
        raise HTTPException(404, f"File not found on disk: {rec.file_path}")

    return FileResponse(
        path       = str(path),
        media_type = "video/mp4",
        filename   = path.name,
        headers    = {"Accept-Ranges": "bytes"},
    )


@router.get("/dates")
def list_dates_with_recordings(
    camera_id: Optional[str] = Query(None),
    days: Optional[int]      = Query(30),
    db: Session              = Depends(get_db_dep),
):
    """
    Return a list of dates (YYYY-MM-DD) that have at least one recording.
    Used by the calendar UI to highlight days with footage.
    """
    since = datetime.utcnow() - timedelta(days=days or 30)
    q = db.query(Recording).filter(
        Recording.status == "completed",
        Recording.start_time >= since,
    )
    if camera_id:
        q = q.filter(Recording.camera_id == camera_id)

    rows = q.all()
    dates = sorted(set(r.start_time.strftime("%Y-%m-%d") for r in rows if r.start_time))
    return {"dates": dates}
