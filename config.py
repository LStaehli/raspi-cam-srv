"""
Central configuration — all values come from environment variables so that
secrets never live in source code.  Copy .env.example to .env and fill in.
"""

import os
import secrets


class Config:
    # ------------------------------------------------------------------ #
    #  Network                                                             #
    # ------------------------------------------------------------------ #
    HOST: str = os.environ.get("CAM_HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("CAM_PORT", "8080"))

    # ------------------------------------------------------------------ #
    #  TLS / HTTPS                                                         #
    # ------------------------------------------------------------------ #
    TLS_ENABLED: bool = os.environ.get("CAM_TLS", "false").lower() == "true"
    TLS_CERT: str = os.environ.get("CAM_TLS_CERT", "certs/server.crt")
    TLS_KEY: str = os.environ.get("CAM_TLS_KEY", "certs/server.key")

    # ------------------------------------------------------------------ #
    #  Authentication                                                      #
    # ------------------------------------------------------------------ #
    # If CAM_USERNAME / CAM_PASSWORD are not set a random token is printed
    # at startup and used as the password (username = "admin").
    AUTH_USERNAME: str = os.environ.get("CAM_USERNAME", "admin")
    AUTH_PASSWORD: str = os.environ.get("CAM_PASSWORD", "")

    # ------------------------------------------------------------------ #
    #  Camera                                                              #
    # ------------------------------------------------------------------ #
    # Set CAM_MOCK=true when developing on a machine without a camera.
    MOCK_CAMERA: bool = os.environ.get("CAM_MOCK", "false").lower() == "true"

    CAMERA_WIDTH: int = int(os.environ.get("CAM_WIDTH", "1280"))
    CAMERA_HEIGHT: int = int(os.environ.get("CAM_HEIGHT", "720"))
    CAMERA_FPS: int = int(os.environ.get("CAM_FPS", "15"))

    # ------------------------------------------------------------------ #
    #  Streaming                                                           #
    # ------------------------------------------------------------------ #
    # Supported: mjpeg | snapshot | hls
    DEFAULT_FORMAT: str = os.environ.get("CAM_FORMAT", "mjpeg").lower()

    MJPEG_QUALITY: int = int(os.environ.get("CAM_MJPEG_QUALITY", "75"))

    # HLS output directory (must be served as static files)
    HLS_DIR: str = os.environ.get("CAM_HLS_DIR", "/tmp/cam_hls")
    HLS_SEGMENT_DURATION: int = int(os.environ.get("CAM_HLS_SEGMENT", "2"))

    # ------------------------------------------------------------------ #
    #  Rate limiting                                                       #
    # ------------------------------------------------------------------ #
    RATELIMIT_DEFAULT: str = os.environ.get("CAM_RATELIMIT", "60 per minute")
    RATELIMIT_STREAM: str = os.environ.get("CAM_RATELIMIT_STREAM", "5 per minute")

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    @classmethod
    def ensure_password(cls) -> str:
        """Return the configured password, generating one if not set."""
        if not cls.AUTH_PASSWORD:
            cls.AUTH_PASSWORD = secrets.token_urlsafe(16)
            print(
                f"\n[WARNING] No CAM_PASSWORD set.  Auto-generated password: "
                f"{cls.AUTH_PASSWORD}\n"
                f"          Username: {cls.AUTH_USERNAME}\n"
                f"          Set CAM_PASSWORD in your .env to silence this.\n"
            )
        return cls.AUTH_PASSWORD
