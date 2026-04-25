"""
HTTP routes.

Endpoints
---------
GET  /                    – Web UI (format chooser + live view)
GET  /stream/mjpeg        – MJPEG multipart stream
GET  /stream/snapshot     – Single JPEG snapshot
GET  /stream/hls          – HLS playlist (redirect or start ffmpeg)
GET  /hls/<path:filename> – Serve HLS segments
GET  /health              – Public health-check (no auth)
POST /api/config          – Update runtime camera settings
GET  /api/config          – Read current settings
"""

from __future__ import annotations

import os

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template_string,
    request,
    send_from_directory,
)

from app import limiter
from app.auth import require_auth
from app.camera import get_camera
from app.stream import (
    hls_is_ready,
    hls_playlist_path,
    mjpeg_generator,
    start_hls,
    stop_hls,
)
from config import Config

bp = Blueprint("cam", __name__)

# Module-level camera singleton (started lazily on first request)
_camera = get_camera()
_camera.start()


# --------------------------------------------------------------------------- #
#  Public endpoints                                                            #
# --------------------------------------------------------------------------- #


@bp.route("/health")
def health():
    return jsonify({"status": "ok", "mock": Config.MOCK_CAMERA})


# --------------------------------------------------------------------------- #
#  Web UI                                                                      #
# --------------------------------------------------------------------------- #

_UI_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RasPi Camera</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, sans-serif;
      background: #111;
      color: #eee;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
      padding: 1.5rem;
    }
    h1 { margin-bottom: 1rem; font-size: 1.4rem; letter-spacing: .05em; }
    #format-bar { display: flex; gap: .5rem; margin-bottom: 1rem; }
    button {
      padding: .4rem 1rem;
      border: 1px solid #555;
      background: #222;
      color: #eee;
      border-radius: 4px;
      cursor: pointer;
      font-size: .9rem;
    }
    button.active { background: #0078d4; border-color: #0078d4; }
    button:hover:not(.active) { background: #333; }
    #viewer {
      width: 100%;
      max-width: 960px;
      background: #000;
      border-radius: 6px;
      overflow: hidden;
      position: relative;
    }
    #viewer img, #viewer video {
      width: 100%;
      display: block;
    }
    #status {
      margin-top: .75rem;
      font-size: .8rem;
      color: #888;
    }
    #snapshot-link {
      margin-top: .5rem;
      font-size: .85rem;
      color: #4af;
    }
  </style>
</head>
<body>
  <h1>RasPi Camera Stream</h1>

  <div id="format-bar">
    <button id="btn-mjpeg" onclick="setFormat('mjpeg')">MJPEG</button>
    <button id="btn-hls"   onclick="setFormat('hls')">HLS (H.264)</button>
    <button id="btn-snap"  onclick="setFormat('snapshot')">Snapshot</button>
  </div>

  <div id="viewer">
    <img id="stream-img" src="" alt="stream" style="display:none">
    <video id="stream-video" autoplay muted playsinline style="display:none"></video>
  </div>

  <p id="status">Select a format above to begin streaming.</p>
  <p id="snapshot-link"></p>

  <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
  <script>
    let hlsInstance = null;
    const img   = document.getElementById('stream-img');
    const video = document.getElementById('stream-video');
    const status = document.getElementById('status');
    const snapLink = document.getElementById('snapshot-link');
    const btns = {
      mjpeg: document.getElementById('btn-mjpeg'),
      hls:   document.getElementById('btn-hls'),
      snapshot: document.getElementById('btn-snap'),
    };

    function clearActive() {
      Object.values(btns).forEach(b => b.classList.remove('active'));
    }

    function teardown() {
      if (hlsInstance) { hlsInstance.destroy(); hlsInstance = null; }
      img.style.display   = 'none';
      video.style.display = 'none';
      img.src  = '';
      video.src = '';
      snapLink.innerHTML = '';
    }

    function setFormat(fmt) {
      teardown();
      clearActive();
      btns[fmt].classList.add('active');

      if (fmt === 'mjpeg') {
        img.style.display = 'block';
        img.src = '/stream/mjpeg';
        status.textContent = 'Streaming MJPEG…';

      } else if (fmt === 'snapshot') {
        img.style.display = 'block';
        const url = '/stream/snapshot?t=' + Date.now();
        img.src = url;
        status.textContent = 'Snapshot captured.';
        snapLink.innerHTML =
          '<a href="' + url + '" download="snapshot.jpg" style="color:#4af">Download</a>';

      } else if (fmt === 'hls') {
        video.style.display = 'block';
        status.textContent = 'Starting HLS stream…';
        fetch('/stream/hls/start', {method: 'POST'})
          .then(() => {
            const src = '/hls/stream.m3u8';
            if (Hls.isSupported()) {
              hlsInstance = new Hls({ lowLatencyMode: true });
              hlsInstance.loadSource(src);
              hlsInstance.attachMedia(video);
              hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
                video.play();
                status.textContent = 'Streaming HLS (H.264)…';
              });
            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
              video.src = src;
              video.play();
              status.textContent = 'Streaming HLS (native)…';
            } else {
              status.textContent = 'HLS not supported by this browser.';
            }
          });
      }
    }

    // Auto-start with default format
    setFormat('{{ default_format }}');
  </script>
</body>
</html>
"""


@bp.route("/")
@require_auth
def index():
    return render_template_string(_UI_TEMPLATE, default_format=Config.DEFAULT_FORMAT)


# --------------------------------------------------------------------------- #
#  Stream endpoints                                                            #
# --------------------------------------------------------------------------- #


@bp.route("/stream/mjpeg")
@require_auth
@limiter.limit(Config.RATELIMIT_STREAM)
def stream_mjpeg():
    return Response(
        mjpeg_generator(_camera),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )


@bp.route("/stream/snapshot")
@require_auth
@limiter.limit("30 per minute")
def stream_snapshot():
    frame = _camera.capture_snapshot()
    if frame is None:
        return Response("Camera not ready", status=503)
    return Response(
        frame,
        mimetype="image/jpeg",
        headers={
            "Content-Disposition": "inline; filename=snapshot.jpg",
            "Cache-Control": "no-store",
        },
    )


@bp.route("/stream/hls/start", methods=["POST"])
@require_auth
def stream_hls_start():
    try:
        start_hls(_camera)
        return jsonify({"status": "started"})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@bp.route("/stream/hls/stop", methods=["POST"])
@require_auth
def stream_hls_stop():
    stop_hls()
    return jsonify({"status": "stopped"})


@bp.route("/hls/<path:filename>")
@require_auth
def serve_hls(filename: str):
    """Serve HLS playlist and segments from the HLS output directory."""
    return send_from_directory(Config.HLS_DIR, filename)


# --------------------------------------------------------------------------- #
#  Runtime configuration API                                                   #
# --------------------------------------------------------------------------- #


@bp.route("/api/config", methods=["GET"])
@require_auth
def api_config_get():
    return jsonify(
        {
            "width": Config.CAMERA_WIDTH,
            "height": Config.CAMERA_HEIGHT,
            "fps": Config.CAMERA_FPS,
            "quality": Config.MJPEG_QUALITY,
            "default_format": Config.DEFAULT_FORMAT,
            "mock": Config.MOCK_CAMERA,
            "tls": Config.TLS_ENABLED,
        }
    )


_ALLOWED_FORMATS = {"mjpeg", "snapshot", "hls"}


@bp.route("/api/config", methods=["POST"])
@require_auth
def api_config_set():
    data = request.get_json(silent=True) or {}
    errors = []

    if "quality" in data:
        q = int(data["quality"])
        if not 1 <= q <= 95:
            errors.append("quality must be 1–95")
        else:
            Config.MJPEG_QUALITY = q

    if "format" in data:
        fmt = str(data["format"]).lower()
        if fmt not in _ALLOWED_FORMATS:
            errors.append(f"format must be one of {sorted(_ALLOWED_FORMATS)}")
        else:
            Config.DEFAULT_FORMAT = fmt

    if "fps" in data:
        fps = int(data["fps"])
        if not 1 <= fps <= 90:
            errors.append("fps must be 1–90")
        else:
            Config.CAMERA_FPS = fps

    if errors:
        return jsonify({"errors": errors}), 400

    return jsonify({"status": "ok"})
