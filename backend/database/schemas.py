"""Validated request bodies for settings and backup endpoints."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

SETTINGS_LIMITS: dict[str, tuple[int, int]] = {
    "chat_history_limit": (1, 40),
    "document_top_k": (1, 12),
}


class SettingsUpdate(BaseModel):
    chat_history_limit: int | None = Field(default=None, ge=1, le=40)
    document_top_k: int | None = Field(default=None, ge=1, le=12)

    def changes(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.model_dump().items()
            if value is not None and key in SETTINGS_LIMITS
        }


class BackupRequest(BaseModel):
    include_vectors: bool = True


class RestoreRequest(BaseModel):
    backup_id: str = Field(min_length=1, max_length=200)

    @field_validator("backup_id")
    @classmethod
    def safe_name(cls, value: str) -> str:
        name = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", name):
            raise ValueError("Backup ids look like botforge-20260101-120000.zip.")
        return name
