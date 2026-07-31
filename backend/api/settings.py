"""
api/settings.py — Read and update application configuration.
"""
import os
from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_config, reload_config

router = APIRouter(prefix="/settings", tags=["settings"])

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/config/config.yaml"))


class CameraUpdate(BaseModel):
    id:       str
    name:     str
    rtsp_url: str


class SettingsUpdate(BaseModel):
    cameras:                Optional[list[CameraUpdate]] = None
    segment_seconds:        Optional[int]               = None
    default_retention_days: Optional[int]               = None
    log_level:              Optional[str]               = None


@router.get("")
def get_settings():
    """Return current settings (RTSP URLs are masked for security)."""
    cfg = get_config()
    cameras = []
    for cam in cfg.get("cameras", []):
        # Mask the password in the RTSP URL for display
        url = cam.get("rtsp_url", "")
        masked = _mask_rtsp_password(url)
        cameras.append({
            "id":       cam["id"],
            "name":     cam["name"],
            "rtsp_url": masked,
        })

    return {
        "cameras":                cameras,
        "segment_seconds":        cfg["recording"]["segment_seconds"],
        "default_retention_days": cfg["app"]["default_retention_days"],
        "log_level":              cfg["app"].get("log_level", "info"),
    }


@router.put("")
def update_settings(update: SettingsUpdate):
    """
    Update configuration. Changes are written to config.yaml.
    Note: camera RTSP URLs containing ${ENV_VAR} placeholders are preserved as-is
    if they match the existing placeholder pattern.
    """
    if not CONFIG_PATH.exists():
        raise HTTPException(500, f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH) as f:
        raw = yaml.safe_load(f)

    if update.cameras is not None:
        # Build a map of existing raw values (to preserve env var placeholders)
        existing_raw = {cam["id"]: cam for cam in raw.get("cameras", [])}
        new_cams = []
        for cam_upd in update.cameras:
            existing = existing_raw.get(cam_upd.id, {})
            # Only update rtsp_url if it doesn't look like an env placeholder
            rtsp = cam_upd.rtsp_url
            if rtsp.startswith("rtsp://") and not rtsp.startswith("rtsp://*"):
                new_rtsp = rtsp
            else:
                new_rtsp = existing.get("rtsp_url", rtsp)
            new_cams.append({
                "id":       cam_upd.id,
                "name":     cam_upd.name,
                "rtsp_url": new_rtsp,
            })
        raw["cameras"] = new_cams

    if update.segment_seconds is not None:
        raw["recording"]["segment_seconds"] = update.segment_seconds

    if update.default_retention_days is not None:
        raw["app"]["default_retention_days"] = update.default_retention_days

    if update.log_level is not None:
        raw["app"]["log_level"] = update.log_level

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)

    reload_config()
    return {"ok": True, "message": "Settings saved. Restart recording workers to apply camera URL changes."}


def _mask_rtsp_password(url: str) -> str:
    """Replace the password in rtsp://user:pass@host with ***."""
    import re
    return re.sub(r"(rtsp://[^:]+:)[^@]+(@)", r"\1***\2", url)
