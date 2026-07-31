# CCTV NVR — Self-Hosted Network Video Recorder

A fully self-hosted, LAN-accessible NVR web application.
- **Live view**: 2 CCTV cameras via WebRTC (50-150ms latency target), zero re-encoding
- **Continuous recording**: Segmented MP4 files, `-c copy`, date-organised folders
- **Playback**: Browse by date/camera, play recordings in-browser
- **Manual deletion**: Delete by date or before a date — nothing ever auto-deleted
- **LAN accessible**: Reach from phone, tablet, any device on the same WiFi

---

## Quick Start

### Prerequisites

On your Linux laptop (server):
- Docker + Docker Compose v2
- Node.js 18+ (for building the frontend — one-time)

### Step 1 — Clone and configure

```bash
cd /opt
git clone <repo> cctv-nvr    # or copy the folder here
cd cctv-nvr

# Create your .env file
cp .env.example .env
nano .env   # Fill in your camera RTSP URLs
```

Your `.env` should look like:
```env
CAM1_RTSP_URL=rtsp://admin:password@192.168.1.64:554/stream1
CAM2_RTSP_URL=rtsp://admin:password@192.168.1.65:554/stream1
RECORDINGS_PATH=/home/waltserver/waltcloud/camera_recordings
```

> **Special characters in passwords**: URL-encode them.
> Example: `p@ss:123` → `p%40ss%3A123`
> Full URL: `rtsp://admin:p%40ss%3A123@192.168.1.64:554/stream1`

### Step 2 — Build the frontend (one-time)

```bash
cd frontend
npm install
npm run build      # Output goes to ../backend/static/
cd ..
```

### Step 3 — Start the stack

```bash
docker compose up -d
```

That's it. Open a browser and go to:
```
http://<your-laptop-LAN-IP>:8000
```

To find your LAN IP: `hostname -I | awk '{print $1}'`

---

## Or: Use the automated setup script

```bash
bash scripts/setup.sh
```

This handles everything: building frontend, starting Docker, installing systemd service, opening firewall ports.

---

## Directory Structure

```
/home/waltserver/waltcloud/camera_recordings/
├── cam1/
│   ├── 2026-07-31/
│   │   ├── 10-00-00.mp4
│   │   ├── 11-00-00.mp4
│   │   └── ...
│   └── 2026-08-01/
│       └── ...
└── cam2/
    └── ...
```

Each file is a 1-hour MP4 segment, `-c copy` (no re-encoding), named by start time.

---

## LAN Access

| Service | Port | URL |
|---------|------|-----|
| Web UI + API | 8000 | `http://<laptop-ip>:8000` |
| go2rtc WHEP | 1984 | `http://<laptop-ip>:1984` |
| WebRTC media | 8555 | TCP + UDP |

### Firewall (if ufw is active)

```bash
sudo ufw allow 8000/tcp
sudo ufw allow 1984/tcp
sudo ufw allow 8555/tcp
sudo ufw allow 8555/udp
```

### Static IP recommendation

Set a DHCP reservation for your server laptop on your router so the URL
(`http://192.168.x.x:8000`) doesn't change across reboots.

---

## Auto-Start on Boot

### Option A — systemd (recommended)

```bash
sudo cp systemd/cctv-nvr.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cctv-nvr
sudo systemctl start cctv-nvr
```

### Option B — Docker restart policy

The `docker-compose.yml` already sets `restart: always` on all services.
If Docker itself is configured to start on boot (default on most distros), the
containers will auto-start.

```bash
sudo systemctl enable docker
```

---

## Camera Configuration

### Keyframe interval (critical for low latency)

For the 50-150ms WebRTC latency target, your cameras must have their
**keyframe interval (GOP) set to ≤ 1 second** (e.g. 1s at 25fps = 25 frames).

Check your camera's web admin panel → Video Settings → GOP / Keyframe Interval.

The backend probes your cameras on startup and logs a warning if:
- The codec is H.265/HEVC (not supported by browsers via WebRTC — use H.264)
- The keyframe interval is > 1 second

Check the logs: `docker compose logs backend`

### H.265/HEVC warning

If the startup log shows:
```
⚠️ CAMERA USES H.265/HEVC — browsers cannot decode H.265 via WebRTC natively!
```

Fix: Log into the camera's web admin panel and switch the stream to H.264.

---

## Managing the Stack

```bash
# View logs
docker compose logs -f

# View backend logs only
docker compose logs -f backend

# Restart (e.g. after editing .env or config.yaml)
docker compose restart

# Stop
docker compose down

# Update (pull new images)
docker compose pull && docker compose up -d
```

---

## Configuration Reference

### `.env` — Camera credentials

```env
CAM1_RTSP_URL=rtsp://...
CAM2_RTSP_URL=rtsp://...
RECORDINGS_PATH=/home/waltserver/waltcloud/camera_recordings
```

### `config/config.yaml` — Application settings

```yaml
cameras:
  - id: cam1
    name: "Camera 1"
    rtsp_url: "${CAM1_RTSP_URL}"    # reads from .env

recording:
  segment_seconds: 3600     # 1 hour per file

app:
  backend_port: 8000
  default_retention_days: 7
```

---

## Architecture

```
Browser → go2rtc (WHEP, port 1984) → RTSP camera [live view, 50-150ms]
Browser → FastAPI (port 8000) → SQLite DB           [API]
FastAPI → ffmpeg workers → /recordings/             [recording]
FastAPI → /backend/static/                          [frontend SPA]
```

All services use `network_mode: host` so WebRTC ICE negotiation works
correctly on LAN without a STUN/TURN server.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Live view shows "Connecting" forever | go2rtc not ready, or camera H.265 | Check `docker logs cctv-go2rtc` |
| Latency > 500ms | Camera keyframe interval too long | Set GOP to 1s on camera |
| Recording not starting | Wrong RTSP URL | Check `docker logs cctv-backend` |
| Can't reach from phone | Firewall blocking | Run ufw allow commands above |
| Port 8000 in use | Another app | Change `backend_port` in config.yaml |
