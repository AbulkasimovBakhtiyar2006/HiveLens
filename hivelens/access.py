"""Password access for a small shared deployment, not per-user data isolation."""
from __future__ import annotations

import hashlib
import hmac
from http.cookies import CookieError, SimpleCookie
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

from . import config

COOKIE = "hivelens_session"
TTL = 8 * 60 * 60
_attempts: dict[str, list[float]] = {}
_lock = threading.Lock()


def _signature(value: str) -> str:
    return hmac.new(config.AUTH_PASSWORD.encode(), (config.AUTH_USER + ":" + value).encode(), hashlib.sha256).hexdigest()


def session_valid(cookie: str) -> bool:
    if not config.AUTH_PASSWORD:
        return False
    try:
        jar = SimpleCookie()
        jar.load(cookie)
        token = jar[COOKIE].value
        expiry, nonce, signature = token.split(".")
        return int(expiry) > time.time() and hmac.compare_digest(signature, _signature(expiry + "." + nonce))
    except (KeyError, ValueError, AttributeError, CookieError):
        return False


def same_origin(handler) -> bool:
    origin = handler.headers.get("Origin")
    if not origin:
        return True  # CLI clients may omit Origin; they still need a valid session.
    parsed = urlsplit(origin)
    return parsed.scheme in ("https", "http") and parsed.netloc == handler.headers.get("Host")


def can_write(handler) -> bool:
    return not config.AUTH_PASSWORD or session_valid(handler.headers.get("Cookie", ""))


def public_read_path(path: str) -> bool:
    # Explicit read-only routes; job streams and owner profile photos remain private.
    return path in ("/", "/index.html", "/api/state", "/api/settings", "/api/usage", "/api/research/mustb") or path.startswith((
        "/static/", "/api/weather/", "/api/demo_asset/", "/api/hive/",
        "/api/file/", "/api/sample_preview/", "/api/export/",
    ))


def _redirect(handler, location: str, cookie: str | None = None) -> None:
    handler.send_response(303)
    handler.send_header("Location", location)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", "0")
    if cookie:
        handler.send_header("Set-Cookie", cookie)
    handler.end_headers()


def _cookie(value: str, age: int) -> str:
    return f"{COOKIE}={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}" + ("; Secure" if config.SECURE_COOKIES else "")


def _login_page(handler, error: str = "", status: int = 200) -> None:
    # error is a fixed server string, never user-controlled input.
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · HiveLens</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#fffdf6;color:#2f291d;font:16px/1.6 system-ui,sans-serif;min-height:100vh;display:grid;place-items:center;padding:24px}}main{{width:100%;max-width:420px}}.brand{{font-weight:650}}h1{{font-size:32px;letter-spacing:-1px;margin:36px 0 8px}}p{{color:#746953}}label{{display:block;margin:20px 0 6px}}input,button{{width:100%;font:inherit;border-radius:10px;padding:12px 14px}}input{{border:1px solid #d8cfba;background:white}}input:focus{{outline:2px solid #b78a1a;outline-offset:2px}}button{{border:0;background:#f2c43d;color:#2f291d;font-weight:600;margin-top:26px;cursor:pointer}}.error{{color:#a63423}}small{{color:#746953;display:block;margin-top:24px}}</style></head>
<body><main><div class="brand">HiveLens</div><h1>Welcome back.</h1><p>Sign in to explore the evidence and run a hive inspection.</p>
{f'<p class="error" role="alert">{error}</p>' if error else ''}
<form method="post" action="/login"><label for="username">Username</label><input id="username" name="username" autocomplete="username" required autofocus maxlength="100">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="200">
<button type="submit">Sign in</button></form><small>Private demo workspace · Ask the project owner for access.</small></main></body></html>'''.encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
    handler.end_headers()
    handler.wfile.write(body)


def authorize(handler, *, post: bool = False) -> bool:
    """Handle login/logout and reject unauthenticated requests before any app route."""
    if not config.AUTH_PASSWORD:
        return True
    path = urlsplit(handler.path).path
    if path == "/healthz" and not post:
        return True
    if post and not same_origin(handler):
        handler._send_json({"error": "Cross-site request rejected."}, 403)
        return False
    if path == "/login":
        if not post:
            _login_page(handler)
            return False
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError
            form = parse_qs(handler.rfile.read(length).decode())
        except (ValueError, UnicodeError):
            handler.close_connection = True
            _login_page(handler, "Invalid sign-in request.", 400)
            return False
        # Use the socket peer instead of trusting a client-supplied forwarded IP.
        peer = handler.client_address[0]
        now = time.monotonic()
        with _lock:
            for key in list(_attempts):
                _attempts[key] = [t for t in _attempts[key] if t > now - 60]
                if not _attempts[key]:
                    del _attempts[key]
            attempts = _attempts.setdefault(peer, [])
            blocked = len(attempts) >= 10
            if not blocked:
                attempts.append(now)
        if blocked:
            _login_page(handler, "Too many attempts. Try again in one minute.", 429)
            return False
        user_ok = hmac.compare_digest(form.get("username", [""])[0].encode(), config.AUTH_USER.encode())
        pass_ok = hmac.compare_digest(form.get("password", [""])[0].encode(), config.AUTH_PASSWORD.encode())
        if not (user_ok and pass_ok):
            _login_page(handler, "Username or password is incorrect.", 401)
            return False
        value = f"{int(time.time()) + TTL}.{secrets.token_hex(16)}"
        _redirect(handler, "/", _cookie(value + "." + _signature(value), TTL))
        return False
    if not post and config.PUBLIC_READ and public_read_path(path):
        return True
    if not can_write(handler):
        if post or path.startswith("/api/"):
            handler._send_json({"error": "Owner sign-in is required to run analyses or change shared data. Saved results are available without signing in.", "login_url": "/login"}, 401)
        else:
            _redirect(handler, "/login")
        return False
    if path == "/logout" and post:
        _redirect(handler, "/login", _cookie("", 0))
        return False
    return True
