"""
api/storage.py — Storage stats and manual deletion endpoints.

All deletions require a 2-step flow:
  1. POST /storage/preview  → returns what would be deleted (count + size)
  2. POST /storage/delete   → performs the actual deletion (same payload)

Nothing is ever deleted automatically.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db_dep, Recording

router = APIRouter(prefix="/storage", tags=["storage"])


# ─── Request models ───────────────────────────────────────────────────────────

class DeleteByDateRequest(BaseModel):
    date:      str            # YYYY-MM-DD
    camera_id: Optional[str] = None   # None = both cameras

class DeleteBeforeDateRequest(BaseModel):
    before_date: str          # YYYY-MM-DD — delete everything BEFORE this date
    camera_id:   Optional[str] = None


# ─── Stats ───────────────────────────────────────────────────────────────────

@router.get("/stats")
def storage_stats(db: Session = Depends(get_db_dep)):
    """
    Return total storage used and a per-camera breakdown.
    Also returns oldest and newest recording date per camera.
    """
    from config import get_cameras
    cameras = get_cameras()

    total_bytes = 0
    camera_stats = []

    for cam in cameras:
        rows = db.query(Recording).filter(
            Recording.camera_id == cam["id"],
            Recording.status    == "completed",
        ).all()

        bytes_used = sum(r.file_size_bytes or 0 for r in rows)
        total_bytes += bytes_used

        start_times = [r.start_time for r in rows if r.start_time]
        oldest = min(start_times).isoformat() if start_times else None
        newest = max(start_times).isoformat() if start_times else None

        camera_stats.append({
            "id":              cam["id"],
            "name":            cam["name"],
            "bytes_used":      bytes_used,
            "recording_count": len(rows),
            "oldest_recording": oldest,
            "newest_recording": newest,
        })

    return {
        "total_bytes":   total_bytes,
        "cameras":       camera_stats,
    }


# ─── Preview helpers ─────────────────────────────────────────────────────────

def _query_by_date(db: Session, date_str: str, camera_id: Optional[str]):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    q = db.query(Recording).filter(
        Recording.start_time >= d,
        Recording.start_time <  d + timedelta(days=1),
        Recording.status     != "gap",
    )
    if camera_id:
        q = q.filter(Recording.camera_id == camera_id)
    return q.all()


def _query_before_date(db: Session, before_str: str, camera_id: Optional[str]):
    try:
        d = datetime.strptime(before_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "before_date must be YYYY-MM-DD")
    q = db.query(Recording).filter(
        Recording.start_time < d,
        Recording.status     != "gap",
    )
    if camera_id:
        q = q.filter(Recording.camera_id == camera_id)
    return q.all()


def _summarise(rows: list) -> dict:
    total_size = sum(r.file_size_bytes or 0 for r in rows)
    return {
        "count":       len(rows),
        "total_bytes": total_size,
        "recordings":  [
            {
                "id":         r.id,
                "camera_id":  r.camera_id,
                "file_path":  r.file_path,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "size_bytes": r.file_size_bytes,
            }
            for r in rows
        ],
    }


# ─── Preview endpoints ────────────────────────────────────────────────────────

@router.post("/preview/date")
def preview_delete_by_date(
    req: DeleteByDateRequest,
    db: Session = Depends(get_db_dep),
):
    """Dry-run: show what would be deleted for a specific date."""
    rows = _query_by_date(db, req.date, req.camera_id)
    return _summarise(rows)


@router.post("/preview/before")
def preview_delete_before_date(
    req: DeleteBeforeDateRequest,
    db: Session = Depends(get_db_dep),
):
    """Dry-run: show what would be deleted before a cutoff date."""
    rows = _query_before_date(db, req.before_date, req.camera_id)
    return _summarise(rows)


# ─── Delete endpoints ────────────────────────────────────────────────────────

def _do_delete(db: Session, rows: list) -> dict:
    """Delete files from disk and remove their DB rows. Returns summary."""
    deleted_count = 0
    deleted_bytes = 0
    errors = []

    for rec in rows:
        path = Path(rec.file_path)
        try:
            if path.exists():
                os.remove(path)
                deleted_bytes += rec.file_size_bytes or 0
            # Remove from DB even if file was already missing
            db.delete(rec)
            deleted_count += 1
        except OSError as e:
            errors.append({"file": str(path), "error": str(e)})

    return {
        "deleted_count": deleted_count,
        "deleted_bytes": deleted_bytes,
        "errors":        errors,
    }


@router.post("/delete/date")
def delete_by_date(
    req: DeleteByDateRequest,
    db: Session = Depends(get_db_dep),
):
    """
    Permanently delete all recordings for a specific date (and optionally a specific camera).
    Files are removed from disk AND the database.
    """
    rows = _query_by_date(db, req.date, req.camera_id)
    if not rows:
        return {"deleted_count": 0, "deleted_bytes": 0, "errors": []}
    result = _do_delete(db, rows)
    return result


@router.post("/delete/before")
def delete_before_date(
    req: DeleteBeforeDateRequest,
    db: Session = Depends(get_db_dep),
):
    """
    Permanently delete all recordings before a cutoff date (and optionally a specific camera).
    Files are removed from disk AND the database.
    """
    rows = _query_before_date(db, req.before_date, req.camera_id)
    if not rows:
        return {"deleted_count": 0, "deleted_bytes": 0, "errors": []}
    result = _do_delete(db, rows)
    return result
