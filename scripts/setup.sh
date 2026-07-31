#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  CCTV NVR — First-Run Setup Script
#  Run this once on the Linux server to deploy the app.
#  Usage: bash scripts/setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

INSTALL_DIR="/opt/cctv-nvr"
SERVICE_NAME="cctv-nvr"
RECORDINGS_PATH="/home/waltserver/waltcloud/camera_recordings"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         CCTV NVR Setup                               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ─── 1. Check dependencies ────────────────────────────────────────────────────
echo "▶ Checking dependencies..."

if ! command -v docker &>/dev/null; then
    echo "  ✗ Docker not found. Install it first:"
    echo "    curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "  ✗ Docker Compose v2 not found. Update Docker."
    exit 1
fi

echo "  ✓ Docker $(docker --version | awk '{print $3}' | tr -d ',')"
echo "  ✓ Docker Compose $(docker compose version --short)"

# ─── 2. Create install directory ─────────────────────────────────────────────
echo ""
echo "▶ Installing to $INSTALL_DIR ..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp -r . "$INSTALL_DIR/"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"

# ─── 3. Create recordings directory ──────────────────────────────────────────
echo ""
echo "▶ Creating recordings directory: $RECORDINGS_PATH"
mkdir -p "$RECORDINGS_PATH"/{cam1,cam2}
echo "  ✓ Directories created"

# ─── 4. Set up .env ──────────────────────────────────────────────────────────
echo ""
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo "  ✓ Created .env from template"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  ACTION REQUIRED: Edit the .env file with your      │"
    echo "  │  camera RTSP URLs before continuing.                │"
    echo "  │                                                     │"
    echo "  │  nano $INSTALL_DIR/.env                             │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""
    read -p "  Press ENTER when you have edited .env to continue..."
else
    echo "  ✓ .env already exists"
fi

# ─── 5. (Optional) Build frontend ────────────────────────────────────────────
echo ""
echo "▶ Building frontend ..."
if command -v node &>/dev/null; then
    cd "$INSTALL_DIR/frontend"
    npm install --silent
    npm run build --silent
    echo "  ✓ Frontend built → backend/static/"
    cd "$INSTALL_DIR"
else
    echo "  ⚠ Node.js not found — skipping frontend build."
    echo "    Install Node.js and run: cd frontend && npm install && npm run build"
fi

# ─── 6. Start containers ─────────────────────────────────────────────────────
echo ""
echo "▶ Starting Docker stack ..."
cd "$INSTALL_DIR"
docker compose pull --quiet
docker compose up -d
echo "  ✓ Containers started"

# ─── 7. Install systemd service (auto-start on boot) ─────────────────────────
echo ""
echo "▶ Installing systemd service for auto-start on boot ..."
sudo cp "$INSTALL_DIR/systemd/cctv-nvr.service" /etc/systemd/system/
# Update WorkingDirectory in the service file
sudo sed -i "s|/opt/cctv-nvr|$INSTALL_DIR|g" /etc/systemd/system/cctv-nvr.service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "  ✓ systemd service enabled: cctv-nvr.service"

# ─── 8. Firewall rules ───────────────────────────────────────────────────────
echo ""
echo "▶ Opening firewall ports (ufw) ..."
if command -v ufw &>/dev/null; then
    sudo ufw allow 8000/tcp comment "CCTV NVR Web UI"    || true
    sudo ufw allow 1984/tcp comment "CCTV go2rtc API"    || true
    sudo ufw allow 8555/tcp comment "CCTV WebRTC media"  || true
    sudo ufw allow 8555/udp comment "CCTV WebRTC media"  || true
    echo "  ✓ ufw rules added"
else
    echo "  ⚠ ufw not found. Open these ports manually:"
    echo "    8000/tcp  — Web UI + API"
    echo "    1984/tcp  — go2rtc WHEP signalling"
    echo "    8555/tcp+udp — WebRTC media"
fi

# ─── 9. Print LAN info ───────────────────────────────────────────────────────
LAN_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Setup complete!                                        ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║   Open from any device on the same WiFi / LAN:          ║"
echo "║                                                          ║"
echo "║     http://$LAN_IP:8000"
echo "║                                                          ║"
echo "║   💡 Tip: Set a static IP / DHCP reservation for this   ║"
echo "║      machine on your router so the URL stays stable.    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Logs:  docker compose logs -f"
echo "  Stop:  docker compose down"
echo "  Start: systemctl start cctv-nvr  (or docker compose up -d)"
echo ""
