"""HTTP Basic Authentication helpers."""

from __future__ import annotations

import functools
from flask import request, Response

from config import Config


def _check_credentials(username: str, password: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    import hmac

    ok_user = hmac.compare_digest(username.encode(), Config.AUTH_USERNAME.encode())
    ok_pass = hmac.compare_digest(password.encode(), Config.AUTH_PASSWORD.encode())
    return ok_user and ok_pass


def _unauthorized() -> Response:
    return Response(
        "Authentication required.",
        401,
        {"WWW-Authenticate": 'Basic realm="RasPi Camera"'},
    )


def require_auth(f):
    """Decorator that enforces HTTP Basic Auth on a route."""

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not _check_credentials(auth.username, auth.password):
            return _unauthorized()
        return f(*args, **kwargs)

    return decorated
