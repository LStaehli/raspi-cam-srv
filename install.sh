#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  install.sh  –  Set up raspi-cam-srv on a fresh Raspberry Pi (Raspberry Pi OS)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="raspi-cam-srv"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="${SCRIPT_DIR}/.venv"

# ── Parse args ────────────────────────────────────────────────────────────────
GEN_CERTS=false
UNINSTALL=false

for arg in "$@"; do
  case "$arg" in
    --gen-certs) GEN_CERTS=true ;;
    --uninstall) UNINSTALL=true ;;
    -h|--help)
      echo "Usage: $0 [--gen-certs] [--uninstall]"
      echo "  --gen-certs   Generate a self-signed TLS certificate in ./certs/"
      echo "  --uninstall   Stop and remove the systemd service"
      exit 0 ;;
  esac
done

# ── Uninstall ─────────────────────────────────────────────────────────────────
if $UNINSTALL; then
  echo "[uninstall] Stopping and disabling ${SERVICE_NAME}…"
  sudo systemctl stop  "${SERVICE_NAME}" 2>/dev/null || true
  sudo systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
  sudo rm -f "${SERVICE_FILE}"
  sudo systemctl daemon-reload
  echo "[uninstall] Done."
  exit 0
fi

# ── System packages ───────────────────────────────────────────────────────────
echo "[install] Installing system dependencies…"
sudo apt-get update -qq
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  python3-picamera2 \
  ffmpeg \
  libssl-dev

# ── Python virtual environment ────────────────────────────────────────────────
echo "[install] Creating Python virtual environment in ${VENV_DIR}…"
python3 -m venv --system-site-packages "${VENV_DIR}"
# --system-site-packages lets picamera2 (system package) be visible in the venv

"${VENV_DIR}/bin/pip" install --upgrade pip --quiet
"${VENV_DIR}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" --quiet

# ── .env file ─────────────────────────────────────────────────────────────────
if [ ! -f "${SCRIPT_DIR}/.env" ]; then
  echo "[install] Copying .env.example → .env  (edit it before starting!)"
  cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
fi

# ── TLS certificate ───────────────────────────────────────────────────────────
if $GEN_CERTS; then
  echo "[install] Generating self-signed TLS certificate…"
  mkdir -p "${SCRIPT_DIR}/certs"
  openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
    -keyout "${SCRIPT_DIR}/certs/server.key" \
    -out    "${SCRIPT_DIR}/certs/server.crt" \
    -subj   "/CN=raspi-cam-srv" \
    -addext "subjectAltName=IP:0.0.0.0"
  chmod 600 "${SCRIPT_DIR}/certs/server.key"
  echo "[install] Certificate written to ./certs/server.{crt,key}"
  echo "[install] Set CAM_TLS=true in .env to enable HTTPS."
fi

# ── systemd service ───────────────────────────────────────────────────────────
echo "[install] Writing systemd service to ${SERVICE_FILE}…"
sudo tee "${SERVICE_FILE}" > /dev/null << EOF
[Unit]
Description=RasPi Camera Streaming Server
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${SCRIPT_DIR}
EnvironmentFile=${SCRIPT_DIR}/.env
ExecStart=${VENV_DIR}/bin/gunicorn \
    --bind \$CAM_BIND \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    "run:app"
Restart=on-failure
RestartSec=5

# Hardening
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable  "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo ""
echo "─────────────────────────────────────────────────────"
echo " raspi-cam-srv installed and started!"
echo ""
echo " Status:   sudo systemctl status ${SERVICE_NAME}"
echo " Logs:     journalctl -u ${SERVICE_NAME} -f"
echo " Config:   edit ${SCRIPT_DIR}/.env then sudo systemctl restart ${SERVICE_NAME}"
echo "─────────────────────────────────────────────────────"
