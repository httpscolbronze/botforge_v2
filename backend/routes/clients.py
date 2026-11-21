"""Connected client presence for the Host dashboard.

Presence rows live in SQLite. Clients heartbeat every 30s. This is presence
only - it is not authentication for multi-tenant deployments.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.routes.auth import require_admin
from backend.storage import repositories
from backend.storage.repositories import ACTIVE_WINDOW_SECONDS

logger = logging.getLogger("botforge.clients")
router = APIRouter(tags=["clients"])


class Heartbeat(BaseModel):
    client_id: str = Field(min_length=1, max_length=64)
    name: str = Field(default="Local workspace", max_length=80)
    mode: str = Field(default="client", max_length=16)


@router.post("/clients/heartbeat")
async def heartbeat(payload: Heartbeat) -> dict:
    active = repositories.heartbeat_client(payload.client_id, payload.name, payload.mode)
    return {"ok": True, "active": active}


@router.get("/clients")
async def list_clients(_: dict = Depends(require_admin)) -> dict:
    items = repositories.active_clients()
    return {
        "clients": items,
        "count": len(items),
        "window_seconds": ACTIVE_WINDOW_SECONDS,
    }
