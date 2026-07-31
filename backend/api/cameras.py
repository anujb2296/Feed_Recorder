"""
api/cameras.py — Camera status and codec info endpoints.
"""
from fastapi import APIRouter

from config import get_cameras
from recording.manager import get_manager

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("")
def list_cameras():
    """
    Return all configured cameras with their current recording status
    and codec information (from the startup ffprobe probe).
    """
    cameras  = get_cameras()
    manager  = get_manager()

    result = []
    for cam in cameras:
        status     = "offline"
        codec_info = {}

        if manager:
            status     = manager.get_camera_status(cam["id"])
            codec_info = manager.get_codec_info(cam["id"]) or {}

        result.append({
            "id":                 cam["id"],
            "name":               cam["name"],
            "status":             status,
            "codec":              codec_info.get("codec"),
            "fps":                codec_info.get("fps"),
            "width":              codec_info.get("width"),
            "height":             codec_info.get("height"),
            "keyframe_interval_sec": codec_info.get("keyframe_interval_sec"),
        })

    return result


@router.get("/{camera_id}/status")
def camera_status(camera_id: str):
    """Return the current recording status for a single camera."""
    manager = get_manager()
    if not manager:
        return {"camera_id": camera_id, "status": "offline"}
    return {
        "camera_id": camera_id,
        "status":    manager.get_camera_status(camera_id),
    }
