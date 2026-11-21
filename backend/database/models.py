"""Table metadata and row -> API dictionary mapping.

The schema itself lives in ``migrations/`` so it can evolve with numbered,
idempotent migration files. Table names are declared here so repositories and
health checks do not repeat string literals.
"""

from __future__ import annotations

import json
from typing import Any

# Tables created by the migrations, in dependency order.
TABLES: tuple[str, ...] = (
    "users",
    "personas",
    "agents",
    "conversations",
    "messages",
    "host_policies",
    "documents",
    "document_grants",
    "audit_logs",
    "app_settings",
    "client_presence",
)

DEFAULT_POLICY_ID = "default"
DEFAULT_CHAT_MODEL = "llama3.2:3b"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"


def loads(value: str | None, default: Any) -> Any:
    """Parse a JSON column, returning ``default`` when absent or corrupt."""
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def persona_from_row(row: Any) -> dict[str, Any]:
    """Map a personas row to the dictionary shape the API has always used."""
    return {
        "id": row["id"],
        "client_id": row["owner_id"],
        "name": row["name"],
        "persona": row["role"],
        "tone": row["tone"],
        "response_style": row["response_style"],
        "expertise": row["expertise"],
        "language": row["language"],
        "additional_instructions": row["additional_instructions"],
        "is_default": bool(row["is_default"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def agent_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "persona_id": row["persona_id"],
        "name": row["name"],
        "description": row["description"],
        "chat_model": row["chat_model"],
        "embedding_model": row["embedding_model"],
        "config": loads(row["config_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def document_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["owner_id"],
        "name": row["name"],
        "extension": row["extension"],
        "size_bytes": row["size_bytes"],
        "pages": row["pages"],
        "chunks": row["chunks"],
        "embedding_provider": row["embedding_provider"],
        "embedding_model": row["embedding_model"],
        "stored_path": row["stored_path"],
        "checksum": row["checksum"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def message_from_row(row: Any) -> dict[str, Any]:
    message: dict[str, Any] = {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
    }
    sources = loads(row["sources_json"], None)
    if sources:
        message["sources"] = sources
    if row["model"]:
        message["model"] = row["model"]
    return message


def policy_from_row(row: Any) -> dict[str, Any]:
    return {
        "org_purpose": row["org_purpose"],
        "allowed_topics": loads(row["allowed_topics_json"], []),
        "restricted_topics": loads(row["restricted_topics_json"], []),
        "document_access": bool(row["document_access"]),
        "screen_analysis": bool(row["screen_analysis"]),
        "external_voice": bool(row["external_voice"]),
        "system_rules": row["system_rules"],
        "max_context_chunks": row["max_context_chunks"],
        "updated_at": row["updated_at"],
        "updated_by": row["updated_by"],
    }
