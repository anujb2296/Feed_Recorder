"""
main.py — FastAPI application entry point for the CCTV NVR backend.

On startup:
  1. Initialise the SQLite database
  2. Reconcile any in-progress recordings from a previous crash
  3. Generate go2rtc.yaml and register streams via go2rtc API
  4. Start recording workers (one per camera) and the directory scanner
  5. Print LAN access URL to stdout

On shutdown:
  6. Gracefully stop all recording workers
"""
import asyncio
import logging
import os
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp
import yaml
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import get_cameras, get_config, get_go2rtc_config, get_app_config
from database import init_db
from recording.manager import RecordingManager, set_manager
from recording.reconciler import reconcile_on_startup
from api import recordings, storage, cameras, settings

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── go2rtc helpers ───────────────────────────────────────────────────────────

GO2RTC_YAML_PATH = Path(os.environ.get("GO2RTC_YAML_PATH", "/config/go2rtc.yaml"))


def _write_go2rtc_yaml(cameras_cfg: list[dict], go2rtc_cfg: dict) -> None:
    """Generate go2rtc.yaml from the application config."""
    streams = {cam["id"]: [cam["rtsp_url"]] for cam in cameras_cfg}
    doc = {
        "streams": streams,
        "api": {
            "origin": "*",       # Allow CORS from browser (port 8000 → port 1984)
        },
        "webrtc": {
            "ice_servers": [],   # LAN-only — no STUN/TURN needed
        },
        "log": {"level": "info"},
    }
    GO2RTC_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GO2RTC_YAML_PATH, "w") as f:
        yaml.dump(doc, f, default_flow_style=False)
    logger.info(f"Written go2rtc.yaml → {GO2RTC_YAML_PATH}")


async def _register_go2rtc_streams(cameras_cfg: list[dict], go2rtc_api: str) -> None:
    """
    Register camera streams with go2rtc via its REST API so they take effect
    immediately without a go2rtc restart.
    Retries for up to 30s while go2rtc is starting up.
    """
    for attempt in range(6):
        try:
            async with aiohttp.ClientSession() as session:
                for cam in cameras_cfg:
                    url = f"{go2rtc_api}/api/streams"
                    params = {"name": cam["id"], "src": cam["rtsp_url"]}
                    async with session.put(url, params=params) as resp:
                        if resp.status in (200, 201, 204):
                            logger.info(f"go2rtc: registered stream [{cam['id']}]")
                        else:
                            body = await resp.text()
                            logger.warning(
                                f"go2rtc: failed to register [{cam['id']}]: "
                                f"{resp.status} {body}"
                            )
            return
        except aiohttp.ClientConnectorError:
            if attempt < 5:
                wait = 5 * (attempt + 1)
                logger.info(f"go2rtc not ready yet, retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                logger.error("go2rtc did not become ready — live view may not work.")


# ─── LAN info printer ─────────────────────────────────────────────────────────

def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _print_lan_info(port: int) -> None:
    ip = _get_lan_ip()
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║               CCTV NVR is running!                          ║
╠══════════════════════════════════════════════════════════════╣
║  Open from any device on the same WiFi / LAN:              ║
║                                                              ║
║    http://{ip}:{port:<5}                                 ║
║                                                              ║
║  Firewall ports to open on this machine:                    ║
║    {port}  (TCP)  — Web UI + API                          ║
║    1984   (TCP)  — go2rtc API + WHEP signalling            ║
║    8555   (TCP + UDP)  — WebRTC media                      ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner, flush=True)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Init DB
    init_db()
    logger.info("Database initialised.")

    # 2. Reconcile crashed recordings
    await reconcile_on_startup()

    # Load config
    cfg         = get_config()
    cameras_cfg = get_cameras()
    go2rtc_cfg  = get_go2rtc_config()
    app_cfg     = get_app_config()

    # 3. Write go2rtc.yaml and register streams
    _write_go2rtc_yaml(cameras_cfg, go2rtc_cfg)
    asyncio.create_task(
        _register_go2rtc_streams(cameras_cfg, go2rtc_cfg["api_url"])
    )

    # 4. Start recording workers
    manager = RecordingManager(cfg)
    set_manager(manager)
    await manager.start_all()

    # 5. Print LAN info
    _print_lan_info(app_cfg["backend_port"])

    yield  # ── App is running ──────────────────────────────

    # 6. Graceful shutdown
    await manager.stop_all()
    logger.info("Shutdown complete.")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="CCTV NVR",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the Vite dev server (port 5173) to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API routes ───────────────────────────────────────────────────────────────
app.include_router(recordings.router, prefix="/api")
app.include_router(storage.router,    prefix="/api")
app.include_router(cameras.router,    prefix="/api")
app.include_router(settings.router,   prefix="/api")


# ─── WHEP Proxy Endpoint ──────────────────────────────────────────────────────
@app.api_route("/api/whep", methods=["POST", "OPTIONS"])
async def whep_proxy(request: Request):
    """Proxy WHEP WebRTC SDP requests directly to go2rtc to prevent CORS issues."""
    if request.method == "OPTIONS":
        return Response(status_code=200)

    dst = request.query_params.get("dst", "")
    body = await request.body()

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"http://localhost:1984/api/whep?dst={dst}",
                data=body,
                headers={"Content-Type": "application/sdp"}
            ) as resp:
                resp_body = await resp.text()
                return Response(
                    content=resp_body,
                    status_code=resp.status,
                    media_type="application/sdp"
                )
        except Exception as e:
            return Response(content=str(e), status_code=500)


# ─── Serve built React frontend ───────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Mount the assets subdirectory (JS/CSS chunks)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        return FileResponse(str(STATIC_DIR / "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def no_frontend():
        return HTMLResponse(
            "<h2>CCTV NVR API is running.</h2>"
            "<p>Frontend not built yet. Run <code>npm run build</code> "
            "inside the <code>frontend/</code> directory, then copy the "
            "<code>dist/</code> output to <code>backend/static/</code>.</p>"
            "<p><a href='/docs'>API Docs →</a></p>"
        )
