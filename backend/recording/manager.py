"""
manager.py — Supervises all camera recording workers and the directory scanner.
             Exposes camera status to the rest of the API.
"""
import asyncio
import logging
from typing import Optional

from recording.worker  import RecordingWorker
from recording.scanner import DirectoryScanner

logger = logging.getLogger(__name__)


class RecordingManager:
    def __init__(self, config: dict):
        self.cameras      = config["cameras"]
        self.rec_cfg      = config["recording"]
        self._workers: dict[str, RecordingWorker] = {}
        self._scanner: Optional[DirectoryScanner] = None
        self._statuses: dict[str, str] = {}
        self._codec_infos: dict[str, dict] = {}

    def _on_status_change(self, camera_id: str, status: str) -> None:
        self._statuses[camera_id] = status

    async def start_all(self) -> None:
        """Probe cameras, then start all recording workers and the scanner."""
        for cam in self.cameras:
            worker = RecordingWorker(
                camera_id      = cam["id"],
                camera_name    = cam["name"],
                rtsp_url       = cam["rtsp_url"],
                storage_path   = self.rec_cfg["storage_path"],
                segment_seconds= self.rec_cfg["segment_seconds"],
                on_status_change=self._on_status_change,
            )

            # Probe first (non-blocking warning; doesn't block recording start)
            logger.info(f"Probing camera [{cam['id']}] ...")
            info = await worker.probe_camera()
            self._codec_infos[cam["id"]] = info
            self._statuses[cam["id"]] = "recording"

            await worker.start()
            self._workers[cam["id"]] = worker

        # Start the background directory scanner
        self._scanner = DirectoryScanner(
            storage_path = self.rec_cfg["storage_path"],
            cameras      = self.cameras,
        )
        await self._scanner.start()
        logger.info("Recording manager: all workers and scanner started.")

    async def stop_all(self) -> None:
        """Stop all workers and the scanner gracefully."""
        for worker in self._workers.values():
            await worker.stop()
        if self._scanner:
            await self._scanner.stop()
        logger.info("Recording manager: all workers stopped.")

    def get_camera_status(self, camera_id: str) -> str:
        return self._statuses.get(camera_id, "offline")

    def get_all_statuses(self) -> dict[str, str]:
        return dict(self._statuses)

    def get_codec_info(self, camera_id: str) -> Optional[dict]:
        return self._codec_infos.get(camera_id)


# Module-level singleton — set by main.py during startup
_manager: Optional[RecordingManager] = None


def set_manager(m: RecordingManager) -> None:
    global _manager
    _manager = m


def get_manager() -> Optional[RecordingManager]:
    return _manager
