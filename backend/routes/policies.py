"""Host policies: read for clients, write only for the administrator."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.engine.policy_engine import (
    PolicyPayload,
    get_policy,
    public_summary,
    save_policy,
)
from backend.routes.auth import optional_admin, require_admin
from backend.storage import repositories

logger = logging.getLogger("botforge.policies")
router = APIRouter(tags=["policies"])


@router.get("/policies")
async def read_policies(is_admin: bool = Depends(optional_admin)) -> dict:
    """Admins get the full policy; clients get the capability summary."""
    policy = get_policy()
    if is_admin:
        return {"admin": True, "policy": policy}
    return {"admin": False, "policy": public_summary(policy)}


@router.put("/policies")
async def update_policies(
    payload: PolicyPayload, admin: dict = Depends(require_admin)
) -> dict:
    stored = save_policy(payload, updated_by=admin.get("sub", "admin"))
    repositories.record_audit(
        "admin",
        "policy.update",
        target_type="host_policy",
        detail={
            "document_access": stored["document_access"],
            "screen_analysis": stored["screen_analysis"],
            "external_voice": stored["external_voice"],
        },
    )
    logger.info(
        "Policy updated (documents=%s, screen=%s, voice=%s)",
        stored["document_access"],
        stored["screen_analysis"],
        stored["external_voice"],
    )
    return {"admin": True, "policy": stored}
