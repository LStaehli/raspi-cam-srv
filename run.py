"""
Entry point.

Usage
-----
  # Development (mock camera, no TLS)
  CAM_MOCK=true python run.py

  # Production on Raspberry Pi
  python run.py

  # With TLS
  CAM_TLS=true CAM_TLS_CERT=certs/server.crt CAM_TLS_KEY=certs/server.key python run.py
"""

from __future__ import annotations

import ssl
import sys

# Load .env automatically if python-dotenv is installed
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from app import create_app
from config import Config

app = create_app()


def _build_ssl_context() -> ssl.SSLContext | None:
    if not Config.TLS_ENABLED:
        return None
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        ctx.load_cert_chain(Config.TLS_CERT, Config.TLS_KEY)
    except FileNotFoundError:
        print(
            f"[ERROR] TLS cert/key not found: {Config.TLS_CERT}, {Config.TLS_KEY}\n"
            f"        Generate self-signed certs with:\n"
            f"          ./install.sh --gen-certs\n"
            f"        or set CAM_TLS=false to disable TLS.",
            file=sys.stderr,
        )
        sys.exit(1)
    return ctx


if __name__ == "__main__":
    ssl_ctx = _build_ssl_context()
    proto = "https" if ssl_ctx else "http"
    print(
        f"[INFO] RasPi Camera Server starting on "
        f"{proto}://{Config.HOST}:{Config.PORT}"
    )
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        ssl_context=ssl_ctx,
        threaded=True,
        debug=False,
    )
