"""Persona + agent configuration storage.

Personas are user data; policy always outranks them. Each persona also owns an
agent row in SQLite (name, description, chat model) so per-agent model
selection survives restarts.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.engine.persona import normalise_persona
from backend.routes.deps import client_id
from backend.storage import repositories

logger = logging.getLogger("botforge.personas")
router = APIRouter(tags=["persona"])

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,120}$")


class PersonaPayload(BaseModel):
    id: str | None = Field(default=None, max_length=64)
    name: str = Field(default="Alex", max_length=120)
    persona: str = Field(default="Senior Software Engineer", max_length=600)
    tone: str = Field(default="Professional", max_length=600)
    response_style: str = Field(default="Detailed and explanatory", max_length=600)
    expertise: str = Field(default="Python, APIs and System Design", max_length=600)
    language: str = Field(default="English", max_length=120)
    additional_instructions: str = Field(default="", max_length=2000)
    chat_model: str | None = Field(default=None, max_length=121)
    embedding_model: str | None = Field(default=None, max_length=121)

    @field_validator("chat_model", "embedding_model")
    @classmethod
    def clean_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not MODEL_RE.match(value):
            raise ValueError(
                "Model names may only contain letters, digits, '.', '_', ':', '/' and '-'."
            )
        return value


@router.get("/personas")
async def list_personas(client: str = Depends(client_id)) -> dict:
    return {"personas": repositories.list_personas(client)}


@router.post("/persona")
async def save_persona(payload: PersonaPayload, client: str = Depends(client_id)) -> dict:
    fields: dict[str, Any] = normalise_persona(payload.model_dump())
    fields.update(
        {
            "chat_model": payload.chat_model,
            "embedding_model": payload.embedding_model,
        }
    )

    if payload.id:
        saved = repositories.update_persona(client, payload.id, fields)
        if not saved:
            raise HTTPException(status_code=404, detail="Persona not found in this workspace.")
        action = "persona.update"
    else:
        saved = repositories.create_persona(client, fields)
        action = "persona.create"

    repositories.record_audit(
        client,
        action,
        target_type="persona",
        target_id=saved["id"],
        detail={"name": saved.get("name"), "chat_model": saved.get("chat_model")},
    )
    logger.info("Persona saved (%s) for workspace %s", saved["id"], client)
    return {"persona": saved}


@router.delete("/personas/{persona_id}")
async def delete_persona(persona_id: str, client: str = Depends(client_id)) -> dict:
    if not repositories.delete_persona(client, persona_id):
        raise HTTPException(status_code=404, detail="Persona not found.")
    repositories.record_audit(
        client, "persona.delete", target_type="persona", target_id=persona_id
    )
    return {"deleted": persona_id}


@router.get("/agents")
async def list_agents(client: str = Depends(client_id)) -> dict:
    """Agent configurations (one per persona) persisted in SQLite."""
    return {"agents": repositories.list_agents(client)}
