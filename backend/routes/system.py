"""Server information and log access for Host Mode."""

from __future__ import annotations

import platform
import time
from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.config import settings
from backend.database.backup import list_backups
from backend.log_buffer import LOG_BUFFER
from backend.rag.retrieval import vector_store
from backend.routes.auth import require_admin
from backend.storage import repositories

router = APIRouter(tags=["system"])
STARTED_AT = time.time()


def _resources() -> dict[str, Any]:
    try:
        import psutil

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(settings.data_dir))
        return {
            "available": True,
            "cpu_percent": psutil.cpu_percent(interval=0.15),
            "cpu_count": psutil.cpu_count(),
            "memory_total_mb": round(memory.total / 1024 / 1024),
            "memory_used_percent": memory.percent,
            "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 1),
        }
    except Exception as exc:  # pragma: no cover - psutil optional
        return {"available": False, "error": f"Resource metrics unavailable: {exc}"}


@router.get("/system/info")
async def system_info(_: dict = Depends(require_admin)) -> dict:
    database = repositories.database_info()
    selected = repositories.selected_models()
    return {
        "app": settings.app_name,
        "version": settings.version,
        "api": {
            "host": settings.host,
            "port": settings.port,
            "bind": f"http://{settings.host}:{settings.port}",
            "loopback_only": settings.host in {"127.0.0.1", "localhost", "::1"},
        },
        "ollama": {
            "base_url": settings.ollama_base_url,
            "default_model": settings.default_model,
            "embedding_model": settings.embedding_model,
            "vision_model": settings.vision_model,
            "selected_chat_model": selected["chat_model"],
            "selected_embedding_model": selected["embedding_model"],
            "selected_vision_model": selected["vision_model"],
            "embedding_fallback": settings.embedding_fallback,
        },
        "data_dir": str(settings.data_dir),
        "database": {
            **database,
            "backup_count": len(list_backups()),
        },
        "counts": database["counts"],
        "vector_store": vector_store.stats(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uptime_seconds": round(time.time() - STARTED_AT),
        },
        "resources": _resources(),
        "security": {
            "default_admin_password": settings.using_default_password,
            "default_session_secret": settings.using_default_session_secret,
            "electron_overlay": False,
        },
    }


@router.get("/system/logs")
async def system_logs(
    _: dict = Depends(require_admin),
    limit: int = Query(default=200, ge=1, le=400),
    level: str | None = Query(default=None),
) -> dict:
    return {"logs": LOG_BUFFER.snapshot(limit=limit, level=level)}
