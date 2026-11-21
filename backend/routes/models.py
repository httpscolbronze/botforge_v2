"""Model discovery and management endpoints.

Discovery is automatic at startup and on demand; selections are persisted in
SQLite and are never changed silently. Pulling a model requires an explicit
confirmation flag from Host Mode.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.config import settings
from backend.engine.model_registry import matches, model_registry
from backend.engine.ollama_client import OllamaError, ollama
from backend.routes.auth import require_admin
from backend.storage import repositories

logger = logging.getLogger("botforge.models")
router = APIRouter(tags=["models"])

MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,120}$")


class ModelName(BaseModel):
    name: str = Field(min_length=1, max_length=121)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not MODEL_NAME_RE.match(value):
            raise ValueError(
                "Model names may only contain letters, digits, '.', '_', ':', '/' and '-'."
            )
        return value


class ModelPull(ModelName):
    confirm: bool = Field(
        default=False,
        description="Must be true: Host Mode confirms the download explicitly.",
    )


class SelectedModels(BaseModel):
    chat_model: str | None = Field(default=None, max_length=121)
    embedding_model: str | None = Field(default=None, max_length=121)
    vision_model: str | None = Field(default=None, max_length=121)

    @field_validator("chat_model", "embedding_model", "vision_model")
    @classmethod
    def valid_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not MODEL_NAME_RE.match(value):
            raise ValueError(
                "Model names may only contain letters, digits, '.', '_', ':', '/' and '-'."
            )
        return value


def _installed(names: list[str], wanted: str) -> bool:
    return matches(names, wanted)


@router.get("/models")
async def list_models() -> dict:
    """Compatibility view used by both modes; enriched with discovery state."""
    snapshot = await model_registry.probe_connection()
    selected = repositories.selected_models()
    running: list[dict[str, Any]] = []
    if snapshot["connected"]:
        running = await ollama.running_models()
    return {
        "connected": snapshot["connected"],
        "base_url": settings.ollama_base_url,
        "version": snapshot["version"],
        "active_model": selected["chat_model"],
        "active_installed": model_registry.available(selected["chat_model"]),
        "models": snapshot["models"],
        "chat_models": snapshot["chat_models"],
        "embedding_models": snapshot["embedding_models"],
        "vision_models": snapshot["vision_models"],
        "running": running,
        "error": snapshot["error"],
        "warning": snapshot["warning"],
        "missing": snapshot["missing"],
        "selected": model_registry.selected_status(),
        "discovered_at": snapshot["discovered_at"],
    }


@router.get("/models/status")
async def models_status() -> dict:
    return model_registry.status()


@router.get("/models/selected")
async def selected_models() -> dict:
    return {"selected": model_registry.selected_status()}


@router.put("/models/selected")
async def update_selected_models(
    payload: SelectedModels, admin: dict = Depends(require_admin)
) -> dict:
    changes = {
        key: value
        for key, value in payload.model_dump().items()
        if value is not None
    }
    if not changes:
        raise HTTPException(status_code=400, detail="Provide at least one model to select.")

    names = [model["name"] for model in model_registry.snapshot()["models"]]
    availability_known = bool(model_registry.snapshot()["connected"] and names)
    for kind, value in changes.items():
        if availability_known and not _installed(names, value):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Model '{value}' is not installed in Ollama. Pull it first, then select it."
                ),
            )

    # Each role is written independently: changing chat never touches embeddings.
    for kind, value in changes.items():
        repositories.set_selected_model(
            kind.replace("_model", ""), value, updated_by=admin.get("sub", "admin")
        )
    repositories.record_audit(
        "admin",
        "models.selected",
        target_type="settings",
        detail=changes,
    )
    logger.info("Model selection updated: %s", changes)
    return {"selected": model_registry.selected_status()}


@router.post("/models/refresh")
async def refresh_models(_: dict = Depends(require_admin)) -> dict:
    snapshot = await model_registry.refresh()
    repositories.record_audit(
        "admin",
        "models.refresh",
        detail={"connected": snapshot["connected"], "models": len(snapshot["models"])},
    )
    return {"status": model_registry.status(), "models": snapshot["models"]}


@router.post("/models/pull")
async def pull_model(payload: ModelPull, _: dict = Depends(require_admin)):
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Model downloads must be confirmed in Host Mode. "
                "Send {name, confirm: true} once the administrator approves the download."
            ),
        )
    logger.info("Pulling Ollama model %s", payload.name)

    async def event_stream():
        yield f"data: {json.dumps({'status': 'starting', 'model': payload.name})}\n\n"
        try:
            async for event in ollama.pull_model(payload.name):
                yield f"data: {json.dumps(event)}\n\n"
            await model_registry.refresh()
            repositories.record_audit(
                "admin", "models.pull", target_type="model", target_id=payload.name
            )
            yield f"data: {json.dumps({'status': 'success', 'model': payload.name})}\n\n"
            logger.info("Finished pulling %s", payload.name)
        except OllamaError as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': exc.message})}\n\n"
        except Exception as exc:  # pragma: no cover - defensive
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/models/active")
async def choose_active_model(payload: ModelName, admin: dict = Depends(require_admin)) -> dict:
    """Legacy alias for selecting the default chat model."""
    return await update_selected_models(
        SelectedModels(chat_model=payload.name), admin
    )


@router.post("/models/load")
async def load_model(payload: ModelName, _: dict = Depends(require_admin)) -> dict:
    try:
        return await ollama.load_model(payload.name)
    except OllamaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/models/unload")
async def unload_model(payload: ModelName, _: dict = Depends(require_admin)) -> dict:
    try:
        return await ollama.unload_model(payload.name)
    except OllamaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
