"""Administrator authentication for Host Mode.

This is deliberately small: a single administrator password from the
environment, exchanged for a short-lived HMAC-signed token. Host Mode settings
are the only thing protected by it, and the server re-validates every write
regardless of what the browser sends.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend.storage import repositories

logger = logging.getLogger("botforge.auth")
router = APIRouter(tags=["auth"])


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload: bytes) -> str:
    return hmac.new(
        settings.session_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()


def create_token(subject: str = "admin", ttl_minutes: int | None = None) -> tuple[str, int]:
    ttl = (ttl_minutes or settings.session_ttl_minutes) * 60
    expires_at = int(time.time()) + ttl
    payload = json.dumps(
        {"sub": subject, "iat": int(time.time()), "exp": expires_at}, separators=(",", ":")
    ).encode("utf-8")
    encoded = _b64encode(payload)
    token = f"{encoded}.{_sign(payload)}"
    return token, expires_at


def verify_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    try:
        payload_bytes = _b64decode(encoded)
    except Exception:
        return None
    if not hmac.compare_digest(_sign(payload_bytes), signature):
        return None
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


async def require_admin(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    payload = verify_token(_bearer(authorization))
    if not payload or payload.get("sub") != "admin":
        raise HTTPException(
            status_code=401,
            detail="Administrator sign-in required. Open Host Mode and enter the admin password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def optional_admin(authorization: str | None = Header(default=None)) -> bool:
    payload = verify_token(_bearer(authorization))
    return bool(payload and payload.get("sub") == "admin")


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login")
async def login(payload: LoginRequest) -> dict[str, Any]:
    expected = settings.admin_password
    if not hmac.compare_digest(payload.password.encode("utf-8"), expected.encode("utf-8")):
        logger.warning("Failed administrator sign-in attempt")
        repositories.record_audit("anonymous", "auth.login_failed")
        raise HTTPException(status_code=401, detail="Incorrect administrator password.")
    repositories.ensure_admin_user()
    repositories.record_audit("admin", "auth.login")
    token, expires_at = create_token()
    logger.info("Administrator signed in")
    return {
        "token": token,
        "expires_at": expires_at,
        "using_default_password": settings.using_default_password,
    }


@router.get("/auth/session")
async def session(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    payload = verify_token(_bearer(authorization))
    return {
        "authenticated": bool(payload and payload.get("sub") == "admin"),
        "expires_at": payload.get("exp") if payload else None,
        "using_default_password": settings.using_default_password,
    }
