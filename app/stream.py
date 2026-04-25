"""
Streaming generators and helpers.

Supported output formats
------------------------
mjpeg     – Motion JPEG multipart stream (browser-native, no plugin needed).
snapshot  – Single JPEG frame (still image).
hls       – HTTP Live Streaming via ffmpeg + picamera2 (H.264, low-latency).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from typing import Generator

from config import Config
from app.camera import BaseCamera


# --------------------------------------------------------------------------- #
#  MJPEG                                                                       #
# --------------------------------------------------------------------------- #

BOUNDARY = b"--frame"


def mjpeg_generator(camera: BaseCamera) -> Generator[bytes, None, None]:
    """Yield multipart JPEG frames suitable for a streaming HTTP response."""
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.05)
            continue
        yield (
            BOUNDARY
            + b"\r\nContent-Type: image/jpeg\r\n"
            + f"Content-Length: {len(frame)}\r\n\r\n".encode()
            + frame
            + b"\r\n"
        )
        time.sleep(1.0 / Config.CAMERA_FPS)


# --------------------------------------------------------------------------- #
#  HLS                                                                         #
# --------------------------------------------------------------------------- #

_hls_lock = threading.Lock()
_hls_proc: subprocess.Popen | None = None


def start_hls(camera: BaseCamera) -> None:
    """
    Start an ffmpeg process that reads raw H.264 from picamera2 and writes
    HLS segments to Config.HLS_DIR.

    On a real Pi, picamera2 can output H.264 directly.  In mock mode we
    use ffmpeg's lavfi test source instead so the endpoint still works.
    """
    global _hls_proc

    with _hls_lock:
        if _hls_proc and _hls_proc.poll() is None:
            return  # already running

        os.makedirs(Config.HLS_DIR, exist_ok=True)
        playlist = os.path.join(Config.HLS_DIR, "stream.m3u8")

        if not shutil.which("ffmpeg"):
            raise RuntimeError(
                "ffmpeg not found.  Install it with:  sudo apt install ffmpeg"
            )

        if Config.MOCK_CAMERA:
            # Use a synthetic test source
            cmd = [
                "ffmpeg",
                "-re",
                "-f", "lavfi",
                "-i", f"testsrc=size={Config.CAMERA_WIDTH}x{Config.CAMERA_HEIGHT}"
                      f":rate={Config.CAMERA_FPS}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-f", "hls",
                "-hls_time", str(Config.HLS_SEGMENT_DURATION),
                "-hls_list_size", "5",
                "-hls_flags", "delete_segments",
                playlist,
            ]
        else:
            # Read from libcamera (picamera2 must not be running concurrently)
            cmd = [
                "ffmpeg",
                "-f", "v4l2",
                "-framerate", str(Config.CAMERA_FPS),
                "-video_size", f"{Config.CAMERA_WIDTH}x{Config.CAMERA_HEIGHT}",
                "-i", "/dev/video0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-f", "hls",
                "-hls_time", str(Config.HLS_SEGMENT_DURATION),
                "-hls_list_size", "5",
                "-hls_flags", "delete_segments",
                playlist,
            ]

        _hls_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def stop_hls() -> None:
    global _hls_proc
    with _hls_lock:
        if _hls_proc and _hls_proc.poll() is None:
            _hls_proc.terminate()
            _hls_proc = None


def hls_playlist_path() -> str:
    return os.path.join(Config.HLS_DIR, "stream.m3u8")


def hls_is_ready() -> bool:
    return os.path.isfile(hls_playlist_path())
