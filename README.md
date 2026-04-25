# raspi-cam-srv

A lightweight Python camera streaming server for the Raspberry Pi with an Element 14 camera board.  
Streams live video over HTTP/HTTPS with authentication, rate limiting, and support for multiple video formats.

---

## Features

- **Three streaming formats** — MJPEG (browser-native), HLS/H.264 (via ffmpeg), and JPEG snapshots
- **HTTP Basic Auth** — credentials loaded from environment variables; auto-generates a password if none is set
- **Optional TLS/HTTPS** — with a self-signed or CA-signed certificate
- **Rate limiting** — per-IP request limits on all endpoints
- **Security headers** — `X-Frame-Options`, `X-Content-Type-Options`, `HSTS` (when TLS is on), `Cache-Control: no-store`
- **Web UI** — format chooser with live preview, no extra client software needed
- **REST config API** — change quality, FPS, and format at runtime without restarting
- **Mock camera** — run and develop locally without any Pi hardware

---

## Requirements

### Raspberry Pi (production)

| Component | Details |
|-----------|---------|
| Hardware | Raspberry Pi 3B+ / 4 / 5 |
| OS | Raspberry Pi OS (Bookworm or Bullseye, 64-bit recommended) |
| Camera | Element 14 / Raspberry Pi Camera Module (CSI connector) |
| Python | 3.10+ (pre-installed on Raspberry Pi OS) |
| System packages | `python3-picamera2`, `ffmpeg` (installed by `install.sh`) |

### Development machine (mock mode)

- Python 3.10+
- No camera hardware required — set `CAM_MOCK=true`

---

## Project structure

```
raspi-cam-srv/
├── app/
│   ├── __init__.py     Flask app factory, security headers, rate limiter
│   ├── auth.py         HTTP Basic Auth (constant-time comparison)
│   ├── camera.py       Camera abstraction: Camera (picamera2) + MockCamera (Pillow)
│   ├── routes.py       All HTTP endpoints
│   └── stream.py       MJPEG generator + HLS via ffmpeg
├── config.py           All configuration from environment variables
├── run.py              Entry point (Flask dev server + optional TLS)
├── requirements.txt    Python dependencies
├── .env.example        Template for your .env secrets file
└── install.sh          Raspberry Pi setup script + systemd service installer
```

---

## Installation on Raspberry Pi OS

### 1. Enable the camera

Open the configuration tool and enable the camera interface:

```bash
sudo raspi-config
# Navigate to: Interface Options → Camera → Enable
# Reboot when prompted
```

Verify the camera is detected:

```bash
libcamera-hello --list-cameras
```

### 2. Clone the repository

```bash
git clone https://github.com/<your-username>/raspi-cam-srv.git
cd raspi-cam-srv
```

### 3. Configure your environment

```bash
cp .env.example .env
nano .env
```

At minimum, set a strong password:

```bash
CAM_PASSWORD=your_strong_password_here
```

See the [Configuration reference](#configuration-reference) section below for all available options.

### 4. (Optional) Generate a self-signed TLS certificate

Skip this step if you plan to use HTTP only or supply your own certificate.

```bash
./install.sh --gen-certs
```

This writes `certs/server.crt` and `certs/server.key`.  
Then set in `.env`:

```bash
CAM_TLS=true
```

> **Note:** Browsers will show a security warning for self-signed certificates.  
> For a trusted certificate, use [Let's Encrypt](https://letsencrypt.org/) with a domain name.

### 5. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The installer will:

1. Install system packages (`python3-picamera2`, `ffmpeg`)
2. Create a Python virtual environment in `.venv/`
3. Install Python dependencies from `requirements.txt`
4. Copy `.env.example` to `.env` (if not already present)
5. Register and start a **systemd service** (`raspi-cam-srv`) that auto-starts on boot

### 6. Verify the service

```bash
sudo systemctl status raspi-cam-srv
```

View live logs:

```bash
journalctl -u raspi-cam-srv -f
```

---

## Accessing the stream

Open a browser and navigate to:

```
http://<raspberry-pi-ip>:8080
```

Or with TLS enabled:

```
https://<raspberry-pi-ip>:8080
```

You will be prompted for the username (`admin` by default) and the password you set in `.env`.

---

## API endpoints

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| `GET` | `/` | yes | Web UI with live stream and format chooser |
| `GET` | `/health` | no | Health check — returns `{"status":"ok"}` |
| `GET` | `/stream/mjpeg` | yes | Motion JPEG multipart stream |
| `GET` | `/stream/snapshot` | yes | Single JPEG frame (downloadable) |
| `POST` | `/stream/hls/start` | yes | Start the ffmpeg HLS encoder |
| `POST` | `/stream/hls/stop` | yes | Stop the ffmpeg HLS encoder |
| `GET` | `/hls/stream.m3u8` | yes | HLS playlist (served with segments) |
| `GET` | `/api/config` | yes | Read current runtime settings |
| `POST` | `/api/config` | yes | Update quality, FPS, or format |

### Config API example

Read current settings:

```bash
curl -u admin:your_password http://<pi-ip>:8080/api/config
```

```json
{
  "default_format": "mjpeg",
  "fps": 15,
  "height": 720,
  "mock": false,
  "quality": 75,
  "tls": false,
  "width": 1280
}
```

Update JPEG quality and FPS:

```bash
curl -u admin:your_password \
     -X POST \
     -H "Content-Type: application/json" \
     -d '{"quality": 85, "fps": 20}' \
     http://<pi-ip>:8080/api/config
```

---

## Configuration reference

All settings are read from environment variables (or your `.env` file).

### Network

| Variable | Default | Description |
|----------|---------|-------------|
| `CAM_HOST` | `0.0.0.0` | Bind address |
| `CAM_PORT` | `8080` | Listening port |

### TLS / HTTPS

| Variable | Default | Description |
|----------|---------|-------------|
| `CAM_TLS` | `false` | Set to `true` to enable HTTPS |
| `CAM_TLS_CERT` | `certs/server.crt` | Path to PEM certificate |
| `CAM_TLS_KEY` | `certs/server.key` | Path to PEM private key |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `CAM_USERNAME` | `admin` | Basic Auth username |
| `CAM_PASSWORD` | _(auto)_ | Basic Auth password — **always set this in production** |

If `CAM_PASSWORD` is empty, a random one-time password is printed to the log at startup.

### Camera

| Variable | Default | Description |
|----------|---------|-------------|
| `CAM_MOCK` | `false` | Set to `true` to use the synthetic mock camera |
| `CAM_WIDTH` | `1280` | Capture width in pixels |
| `CAM_HEIGHT` | `720` | Capture height in pixels |
| `CAM_FPS` | `15` | Target frames per second |

### Streaming

| Variable | Default | Description |
|----------|---------|-------------|
| `CAM_FORMAT` | `mjpeg` | Default format shown in UI: `mjpeg`, `snapshot`, or `hls` |
| `CAM_MJPEG_QUALITY` | `75` | JPEG quality for MJPEG stream (1–95) |
| `CAM_HLS_DIR` | `/tmp/cam_hls` | Directory for HLS playlist and segments |
| `CAM_HLS_SEGMENT` | `2` | HLS segment duration in seconds |

### Rate limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `CAM_RATELIMIT` | `60 per minute` | Default limit applied to all routes |
| `CAM_RATELIMIT_STREAM` | `5 per minute` | Limit for the MJPEG stream endpoint |

---

## Streaming formats

### MJPEG (Motion JPEG)

- Works in all modern browsers with no plugin
- Stream is served as a `multipart/x-mixed-replace` HTTP response
- Higher bandwidth than H.264 but lowest latency
- Quality controlled by `CAM_MJPEG_QUALITY`

### HLS (HTTP Live Streaming — H.264)

- Requires `ffmpeg` to be installed (`sudo apt install ffmpeg`)
- Better compression than MJPEG; suitable for slower connections
- Uses hls.js in the browser for compatibility; falls back to native HLS on Safari/iOS
- Start the encoder via the UI or `POST /stream/hls/start`

### Snapshot

- Returns a single JPEG frame on demand
- Useful for motion detection scripts or periodic monitoring
- Downloadable directly from the browser

---

## Local development (no Raspberry Pi needed)

```bash
# Install dependencies
pip install -r requirements.txt

# Start with mock camera
CAM_MOCK=true CAM_PASSWORD=secret python run.py

# Open http://localhost:8080 — log in with admin / secret
```

The mock camera generates synthetic coloured frames using Pillow, so the full UI and all endpoints work without any hardware.

---

## Service management

| Action | Command |
|--------|---------|
| Start | `sudo systemctl start raspi-cam-srv` |
| Stop | `sudo systemctl stop raspi-cam-srv` |
| Restart | `sudo systemctl restart raspi-cam-srv` |
| View status | `sudo systemctl status raspi-cam-srv` |
| View logs | `journalctl -u raspi-cam-srv -f` |
| Disable autostart | `sudo systemctl disable raspi-cam-srv` |
| Uninstall service | `./install.sh --uninstall` |

After editing `.env`, always restart the service:

```bash
sudo systemctl restart raspi-cam-srv
```

---

## Exposing to the internet

To make the stream accessible from outside your local network:

1. **Port forward** TCP port `8080` (or `CAM_PORT`) on your router to the Pi's local IP.
2. Use a **dynamic DNS** service (e.g. [DuckDNS](https://www.duckdns.org/)) if your ISP assigns a dynamic public IP.
3. Enable **TLS** (`CAM_TLS=true`) with a valid certificate from Let's Encrypt:

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.example.com
```

Then point `.env` to the generated certificate:

```bash
CAM_TLS=true
CAM_TLS_CERT=/etc/letsencrypt/live/your-domain.example.com/fullchain.pem
CAM_TLS_KEY=/etc/letsencrypt/live/your-domain.example.com/privkey.pem
```

---

## Security checklist

- [ ] Set a strong `CAM_PASSWORD` in `.env`
- [ ] Enable TLS (`CAM_TLS=true`) before exposing to the internet
- [ ] Keep Raspberry Pi OS and packages updated (`sudo apt update && sudo apt upgrade`)
- [ ] Restrict the bind address to a specific interface if not all interfaces should be exposed
- [ ] Consider a reverse proxy (nginx, Caddy) in front for additional hardening

---

## License

See [LICENSE](LICENSE).
