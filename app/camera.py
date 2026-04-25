"""
Camera abstraction layer.

On a real Raspberry Pi with picamera2 installed:
    cam = Camera()

On a development machine (or when CAM_MOCK=true):
    cam = MockCamera()

Both expose the same interface so the rest of the code is identical.
"""

from __future__ import annotations

import io
import threading
import time
from abc import ABC, abstractmethod

from config import Config


class BaseCamera(ABC):
    """Common interface for all camera backends."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_frame(self) -> bytes | None:
        """Return the latest JPEG frame (thread-safe)."""
        with self._lock:
            return self._frame

    def capture_snapshot(self) -> bytes | None:
        """Return a single high-quality JPEG snapshot."""
        return self._capture_snapshot_impl()

    # ------------------------------------------------------------------ #
    #  Subclass responsibilities                                           #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _capture_loop(self) -> None:
        """Background thread: continuously update self._frame."""

    @abstractmethod
    def _capture_snapshot_impl(self) -> bytes | None:
        """Capture a single frame; may differ from stream quality."""

    def _store_frame(self, data: bytes) -> None:
        with self._lock:
            self._frame = data


# --------------------------------------------------------------------------- #
#  Real camera (picamera2)                                                     #
# --------------------------------------------------------------------------- #


class Camera(BaseCamera):
    """picamera2-backed camera (runs on Raspberry Pi only)."""

    def __init__(self) -> None:
        super().__init__()
        # Import here so that import errors only surface on Pi hardware
        from picamera2 import Picamera2  # type: ignore[import]
        from picamera2.encoders import JpegEncoder  # type: ignore[import]
        from picamera2.outputs import FileOutput  # type: ignore[import]

        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={
                "size": (Config.CAMERA_WIDTH, Config.CAMERA_HEIGHT),
                "format": "RGB888",
            },
            controls={"FrameRate": Config.CAMERA_FPS},
        )
        self._picam2.configure(config)

    def _capture_loop(self) -> None:
        import io as _io
        from picamera2.encoders import JpegEncoder  # type: ignore[import]
        from picamera2.outputs import FileOutput  # type: ignore[import]

        self._picam2.start()
        try:
            while self._running:
                buf = _io.BytesIO()
                self._picam2.capture_file(buf, format="jpeg")
                self._store_frame(buf.getvalue())
        finally:
            self._picam2.stop()

    def _capture_snapshot_impl(self) -> bytes | None:
        import io as _io

        buf = _io.BytesIO()
        self._picam2.capture_file(buf, format="jpeg")
        return buf.getvalue()


# --------------------------------------------------------------------------- #
#  Mock camera (development / CI)                                              #
# --------------------------------------------------------------------------- #


class MockCamera(BaseCamera):
    """
    Generates synthetic JPEG frames without any hardware.
    Useful for local development and testing.
    """

    _COLORS = [
        (220, 60, 60),    # red
        (60, 200, 60),    # green
        (60, 60, 220),    # blue
        (220, 200, 60),   # yellow
    ]

    def _capture_loop(self) -> None:
        color_idx = 0
        frame_n = 0
        interval = 1.0 / Config.CAMERA_FPS

        while self._running:
            frame = self._make_frame(
                Config.CAMERA_WIDTH,
                Config.CAMERA_HEIGHT,
                self._COLORS[color_idx],
                frame_n,
            )
            self._store_frame(frame)
            color_idx = (color_idx + 1) % len(self._COLORS)
            frame_n += 1
            time.sleep(interval)

    def _capture_snapshot_impl(self) -> bytes | None:
        return self._make_frame(
            Config.CAMERA_WIDTH,
            Config.CAMERA_HEIGHT,
            (80, 80, 200),
            0,
        )

    @staticmethod
    def _make_frame(
        width: int, height: int, color: tuple[int, int, int], frame_n: int
    ) -> bytes:
        """Draw a colored rectangle with frame counter text via Pillow."""
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore[import]

            img = Image.new("RGB", (width, height), color)
            draw = ImageDraw.Draw(img)

            # Dark overlay bar at top
            draw.rectangle([(0, 0), (width, 60)], fill=(0, 0, 0, 180))
            draw.text(
                (10, 10),
                f"RasPi Camera Mock  |  frame #{frame_n}",
                fill=(255, 255, 255),
            )
            # Draw cross-hair
            cx, cy = width // 2, height // 2
            draw.line([(cx - 40, cy), (cx + 40, cy)], fill="white", width=2)
            draw.line([(cx, cy - 40), (cx, cy + 40)], fill="white", width=2)
            draw.ellipse([(cx - 50, cy - 50), (cx + 50, cy + 50)], outline="white", width=2)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=Config.MJPEG_QUALITY)
            return buf.getvalue()
        except ImportError:
            # Minimal fallback without Pillow: a tiny valid JPEG
            return _minimal_jpeg()


def _minimal_jpeg() -> bytes:
    """Return a 1×1 grey JPEG (used only when Pillow is unavailable)."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04"
        b"\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
        b"\x07\"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br"
        b"\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZ"
        b"cdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95"
        b"\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3"
        b"\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca"
        b"\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7"
        b"\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd4P\x00\x00\x00\x1f\xff\xd9"
    )


def get_camera() -> BaseCamera:
    """Instantiate the right camera backend based on Config."""
    if Config.MOCK_CAMERA:
        return MockCamera()
    return Camera()
