"""Application settings, audit trail and backup/restore endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from backend.database.backup import BackupError, create_backup, list_backups, restore_backup
from backend.database.schemas import BackupRequest, RestoreRequest, SettingsUpdate
from backend.routes.auth import require_admin
from backend.storage import repositories

logger = logging.getLogger("botforge.settings")
router = APIRouter(tags=["settings"])


def _settings_payload() -> dict:
    preferences = repositories.all_settings()
    info = repositories.database_info()
    return {
        "settings": {
            "chat_history_limit": preferences["chat_history_limit"],
            "document_top_k": preferences["document_top_k"],
        },
        "models": {
            "chat_model": preferences["chat_model"],
            "embedding_model": preferences["embedding_model"],
            "vision_model": preferences["vision_model"],
            "updated_at": preferences.get("updated_at"),
            "updated_by": preferences.get("updated_by"),
        },
        "storage": {
            "engine": info["engine"],
            "path": info["path"],
            "size_bytes": info["size_bytes"],
            "documents_dir": info["documents_dir"],
            "backups_dir": info["backups_dir"],
            "integrity": info["integrity"],
            "migrations": info["migrations"],
        },
    }


@router.get("/settings")
async def read_settings() -> dict:
    return _settings_payload()


@router.put("/settings")
async def update_settings(
    payload: SettingsUpdate, admin: dict = Depends(require_admin)
) -> dict:
    changes = payload.changes()
    if not changes:
        raise HTTPException(status_code=400, detail="No supported settings were provided.")
    for key, value in changes.items():
        repositories.set_setting(key, value, updated_by=admin.get("sub", "admin"))
    repositories.record_audit("admin", "settings.update", detail=changes)
    logger.info("Application settings updated: %s", changes)
    return _settings_payload()


@router.get("/audit")
async def audit_log(
    _: dict = Depends(require_admin), limit: int = 200
) -> dict:
    return {"audit": repositories.list_audit(limit)}


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------
@router.get("/backups")
async def backups(_: dict = Depends(require_admin)) -> dict:
    return {"backups": list_backups()}


@router.post("/backup")
async def make_backup(
    payload: BackupRequest | None = None, admin: dict = Depends(require_admin)
) -> dict:
    include_vectors = payload.include_vectors if payload else True
    try:
        result = create_backup(include_vectors=include_vectors)
    except BackupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Backup failed")
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}") from exc
    repositories.record_audit(
        "admin",
        "backup.create",
        target_type="backup",
        target_id=(result.get("backup") or {}).get("id"),
        detail={"include_vectors": include_vectors},
    )
    return result


@router.post("/backup/restore")
async def restore(payload: RestoreRequest, admin: dict = Depends(require_admin)) -> dict:
    try:
        result = restore_backup(payload.backup_id)
    except BackupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Restore failed")
        raise HTTPException(status_code=500, detail=f"Restore failed: {exc}") from exc
    repositories.record_audit(
        "admin",
        "backup.restore",
        target_type="backup",
        target_id=payload.backup_id,
        detail={"warnings": result.get("warnings", [])},
    )
    return result
