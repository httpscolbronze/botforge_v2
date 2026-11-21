"""Shared route helpers."""

from __future__ import annotations

import re

from fastapi import Header


async def client_id(x_client_id: str | None = Header(default=None, alias="X-Client-Id")) -> str:
    """Opaque workspace id sent by the browser.

    Documents and personas are scoped to this id so one local workspace cannot
    read another's uploads through the API.
    """
    if not x_client_id:
        return "local"
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", x_client_id)[:64]
    return cleaned or "local"
