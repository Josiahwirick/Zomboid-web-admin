from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Request
from fastapi.responses import RedirectResponse


SESSION_USER = "user"
SESSION_CSRF = "csrf"


def credentials_match(given: str, expected: str) -> bool:
    given_digest = hashlib.sha256(given.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(given_digest, expected_digest)


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get(SESSION_USER))


def require_login(request: Request) -> RedirectResponse | None:
    if is_logged_in(request):
        return None
    return RedirectResponse(url="/login", status_code=303)


def current_user(request: Request) -> str:
    return str(request.session.get(SESSION_USER) or "")


def csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_CSRF)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_CSRF] = token
    return str(token)


def check_csrf(request: Request, token: str | None) -> bool:
    expected = request.session.get(SESSION_CSRF)
    if not expected or not token:
        return False
    return secrets.compare_digest(str(expected), token)


def login_user(request: Request, username: str) -> None:
    request.session[SESSION_USER] = username
    request.session[SESSION_CSRF] = secrets.token_urlsafe(32)


def logout_user(request: Request) -> None:
    request.session.clear()
