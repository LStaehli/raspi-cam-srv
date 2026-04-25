"""Flask application factory."""

from __future__ import annotations

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config

limiter = Limiter(key_func=get_remote_address)


def create_app(cfg: type[Config] = Config) -> Flask:
    cfg.ensure_password()

    app = Flask(__name__, static_folder="../static", static_url_path="/static")
    app.config.from_object(cfg)

    # ------------------------------------------------------------------ #
    #  Security headers                                                    #
    # ------------------------------------------------------------------ #
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if cfg.TLS_ENABLED:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # ------------------------------------------------------------------ #
    #  Rate limiter                                                        #
    # ------------------------------------------------------------------ #
    limiter.init_app(app)

    # ------------------------------------------------------------------ #
    #  Routes                                                              #
    # ------------------------------------------------------------------ #
    from app.routes import bp  # noqa: E402  (avoid circular import)

    app.register_blueprint(bp)

    return app
