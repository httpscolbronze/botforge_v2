"""SQLite-backed repositories.

Every read and write goes through parameterized SQL. Row shapes are mapped to
the dictionaries the existing API and UI already consumed (``client_id`` stays
as an alias for ``owner_id``) so no working behaviour is lost while the JSON
files are replaced by relational storage.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from backend.config import settings
from backend.database.connection import database
from backend.database.models import (
    DEFAULT_POLICY_ID,
    agent_from_row,
    document_from_row,
    dumps,
    loads,
    message_from_row,
    persona_from_row,
    policy_from_row,
)

logger = logging.getLogger("botforge.repositories")

database.initialize()


def new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex
    return f"{prefix}{raw}" if prefix else raw


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ---------------------------------------------------------------------------
# Users / workspaces
# ---------------------------------------------------------------------------
def ensure_user(
    user_id: str, *, role: str = "client", display_name: str | None = None
) -> dict[str, Any]:
    """Create the user row on first sight; updates presence on later visits."""
    now = utc_now()
    username = f"workspace:{user_id}" if role != "admin" else user_id
    with database.transaction() as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            connection.execute(
                "UPDATE users SET last_seen_at = ? WHERE id = ?", (now, user_id)
            )
            result = dict(row)
            result["last_seen_at"] = now
            return result
        connection.execute(
            """
            INSERT INTO users(id, username, display_name, role, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                display_name or ("Administrator" if role == "admin" else f"Workspace {user_id}"),
                role,
                now,
                now,
            ),
        )
    return {
        "id": user_id,
        "username": username,
        "display_name": display_name or user_id,
        "role": role,
        "created_at": now,
        "last_seen_at": now,
    }


def ensure_admin_user() -> dict[str, Any]:
    return ensure_user("admin", role="admin", display_name="Administrator")


def count_users() -> int:
    row = database.query_one("SELECT COUNT(*) AS c FROM users")
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Personas and agent configurations
# ---------------------------------------------------------------------------
PERSONA_FIELDS = (
    "name",
    "role",
    "tone",
    "response_style",
    "expertise",
    "language",
    "additional_instructions",
)


def list_personas(owner: str) -> list[dict[str, Any]]:
    rows = database.query(
        "SELECT * FROM personas WHERE owner_id = ? ORDER BY updated_at DESC", (owner,)
    )
    agents = {
        row["persona_id"]: row
        for row in database.query(
            "SELECT * FROM agents WHERE owner_id = ?", (owner,)
        )
    }
    items = []
    for row in rows:
        persona = persona_from_row(row)
        agent = agents.get(persona["id"])
        persona["chat_model"] = agent["chat_model"] if agent else None
        persona["embedding_model"] = agent["embedding_model"] if agent else None
        items.append(persona)
    return items


def get_persona(owner: str, persona_id: str) -> dict[str, Any] | None:
    row = database.query_one(
        "SELECT * FROM personas WHERE id = ? AND owner_id = ?", (persona_id, owner)
    )
    if not row:
        return None
    persona = persona_from_row(row)
    agent = get_agent_for_persona(owner, persona_id)
    persona["chat_model"] = agent["chat_model"] if agent else None
    persona["embedding_model"] = agent["embedding_model"] if agent else None
    return persona


def create_persona(owner: str, fields: dict[str, Any]) -> dict[str, Any]:
    ensure_user(owner)
    persona_id = new_id("per_")
    now = utc_now()
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO personas(
                id, owner_id, name, role, tone, response_style, expertise,
                language, additional_instructions, is_default, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                persona_id,
                owner,
                fields.get("name") or "Assistant",
                fields.get("persona") or fields.get("role") or "",
                fields.get("tone") or "",
                fields.get("response_style") or "",
                fields.get("expertise") or "",
                fields.get("language") or "",
                fields.get("additional_instructions") or "",
                now,
                now,
            ),
        )
    persona = get_persona(owner, persona_id)
    assert persona is not None
    persona["chat_model"] = _sync_agent_for_persona(owner, persona, fields)
    return persona


def update_persona(owner: str, persona_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    now = utc_now()
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT * FROM personas WHERE id = ? AND owner_id = ?", (persona_id, owner)
        ).fetchone()
        if not row:
            return None
        connection.execute(
            """
            UPDATE personas SET name = ?, role = ?, tone = ?, response_style = ?,
                expertise = ?, language = ?, additional_instructions = ?, updated_at = ?
            WHERE id = ? AND owner_id = ?
            """,
            (
                fields.get("name") or "Assistant",
                fields.get("persona") or "",
                fields.get("tone") or "",
                fields.get("response_style") or "",
                fields.get("expertise") or "",
                fields.get("language") or "",
                fields.get("additional_instructions") or "",
                now,
                persona_id,
                owner,
            ),
        )
    persona = get_persona(owner, persona_id)
    if persona is not None:
        persona["chat_model"] = _sync_agent_for_persona(owner, persona, fields)
    return persona


def _sync_agent_for_persona(
    owner: str, persona: dict[str, Any], fields: dict[str, Any]
) -> str | None:
    """Mirror persona settings into the agents table (agent configuration)."""
    chat_model = (fields.get("chat_model") or "").strip() or None
    embedding_model = (fields.get("embedding_model") or "").strip() or None
    agent_id = f"agent_{persona['id']}"
    now = utc_now()
    with database.transaction() as connection:
        row = connection.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        config = dumps(
            {
                "persona_id": persona["id"],
                "response_style": persona.get("response_style"),
                "language": persona.get("language"),
            }
        )
        if row:
            connection.execute(
                """
                UPDATE agents SET name = ?, description = ?, chat_model = ?,
                    embedding_model = ?, config_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    persona["name"],
                    persona.get("persona") or "",
                    chat_model,
                    embedding_model,
                    config,
                    now,
                    agent_id,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO agents(
                    id, owner_id, persona_id, name, description, chat_model,
                    embedding_model, config_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    owner,
                    persona["id"],
                    persona["name"],
                    persona.get("persona") or "",
                    chat_model,
                    embedding_model,
                    config,
                    now,
                    now,
                ),
            )
    return chat_model


def get_agent_for_persona(owner: str, persona_id: str) -> dict[str, Any] | None:
    row = database.query_one(
        "SELECT * FROM agents WHERE owner_id = ? AND persona_id = ?", (owner, persona_id)
    )
    return agent_from_row(row) if row else None


def list_agents(owner: str) -> list[dict[str, Any]]:
    rows = database.query(
        "SELECT * FROM agents WHERE owner_id = ? ORDER BY updated_at DESC", (owner,)
    )
    return [agent_from_row(row) for row in rows]


def delete_persona(owner: str, persona_id: str) -> bool:
    with database.transaction() as connection:
        cursor = connection.execute(
            "DELETE FROM personas WHERE id = ? AND owner_id = ?", (persona_id, owner)
        )
        connection.execute("DELETE FROM agents WHERE persona_id = ?", (persona_id,))
        return cursor.rowcount > 0


def count_personas() -> int:
    row = database.query_one("SELECT COUNT(*) AS c FROM personas")
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Conversations and messages
# ---------------------------------------------------------------------------
def _conversation_row(connection: Any, owner: str, conversation_id: str) -> Any:
    return connection.execute(
        "SELECT * FROM conversations WHERE id = ? AND owner_id = ?",
        (conversation_id, owner),
    ).fetchone()


def _conversation_dict(connection: Any, row: Any) -> dict[str, Any]:
    messages = [
        message_from_row(message)
        for message in connection.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
            (row["id"],),
        )
    ]
    return {
        "id": row["id"],
        "client_id": row["owner_id"],
        "agent_id": row["agent_id"],
        "persona_id": row["persona_id"],
        "title": row["title"],
        "model": row["model"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "messages": messages,
    }


def get_conversation(owner: str, conversation_id: str) -> dict[str, Any] | None:
    with database.reader() as connection:
        row = _conversation_row(connection, owner, conversation_id)
        return _conversation_dict(connection, row) if row else None


def list_conversations(owner: str) -> list[dict[str, Any]]:
    with database.reader() as connection:
        rows = connection.execute(
            "SELECT * FROM conversations WHERE owner_id = ? AND archived = 0 "
            "ORDER BY updated_at DESC",
            (owner,),
        ).fetchall()
        return [_conversation_dict(connection, row) for row in rows]


def conversation_summaries(owner: str) -> list[dict[str, Any]]:
    rows = database.query(
        """
        SELECT c.id, c.title, c.created_at, c.updated_at, c.model,
               (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id)
                   AS message_count
        FROM conversations c
        WHERE c.owner_id = ? AND c.archived = 0
        ORDER BY c.updated_at DESC
        """,
        (owner,),
    )
    return [dict(row) for row in rows]


def create_conversation(
    owner: str,
    *,
    title: str,
    model: str | None,
    persona_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    ensure_user(owner)
    conversation_id = new_id("cnv_")
    now = utc_now()
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO conversations(
                id, owner_id, agent_id, persona_id, title, model, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (conversation_id, owner, agent_id, persona_id, title, model, now, now),
        )
        row = _conversation_row(connection, owner, conversation_id)
        return _conversation_dict(connection, row)


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    *,
    sources: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> dict[str, Any] | None:
    now = utc_now()
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not row:
            return None
        cursor = connection.execute(
            """
            INSERT INTO messages(conversation_id, role, content, sources_json, model, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content,
                json.dumps(sources, ensure_ascii=False) if sources else None,
                model,
                now,
            ),
        )
        updates = ["updated_at = ?"]
        params: list[Any] = [now]
        if model:
            updates.append("model = ?")
            params.append(model)
        if role == "user":
            count = connection.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE conversation_id = ? AND role = 'user'",
                (conversation_id,),
            ).fetchone()["c"]
            if count == 1:
                title = content.strip().replace("\n", " ")[:70] or "New conversation"
                updates.append("title = ?")
                params.append(title)
        params.append(conversation_id)
        connection.execute(
            f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?", tuple(params)
        )
        message_row = connection.execute(
            "SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return message_from_row(message_row) if message_row else None


def delete_conversation(owner: str, conversation_id: str) -> bool:
    with database.transaction() as connection:
        cursor = connection.execute(
            "DELETE FROM conversations WHERE id = ? AND owner_id = ?",
            (conversation_id, owner),
        )
        return cursor.rowcount > 0


def count_conversations() -> int:
    row = database.query_one("SELECT COUNT(*) AS c FROM conversations")
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Documents and permissions
# ---------------------------------------------------------------------------
def list_documents(owner: str) -> list[dict[str, Any]]:
    rows = database.query(
        "SELECT * FROM documents WHERE owner_id = ? ORDER BY created_at DESC", (owner,)
    )
    return [document_from_row(row) for row in rows]


def list_accessible_documents(owner: str) -> list[dict[str, Any]]:
    rows = database.query(
        """
        SELECT DISTINCT d.* FROM documents d
        LEFT JOIN document_grants g ON g.document_id = d.id
        WHERE d.owner_id = ? OR g.user_id = ?
        ORDER BY d.created_at DESC
        """,
        (owner, owner),
    )
    return [document_from_row(row) for row in rows]


def get_document(document_id: str) -> dict[str, Any] | None:
    row = database.query_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    return document_from_row(row) if row else None


def create_document(record: dict[str, Any]) -> dict[str, Any]:
    owner = str(record["client_id"])
    ensure_user(owner)
    now = utc_now()
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO documents(
                id, owner_id, name, extension, size_bytes, pages, chunks,
                embedding_provider, embedding_model, stored_path, checksum,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                owner,
                record["name"],
                record["extension"],
                int(record.get("size_bytes") or 0),
                int(record.get("pages") or 0),
                int(record.get("chunks") or 0),
                record.get("embedding_provider"),
                record.get("embedding_model"),
                record["stored_path"],
                record.get("checksum"),
                record.get("status") or "indexed",
                record.get("created_at") or now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO document_grants(document_id, user_id, permission, granted_at)
            VALUES (?, ?, 'read', ?)
            """,
            (record["id"], owner, now),
        )
    return record


def delete_document_record(document_id: str) -> bool:
    with database.transaction() as connection:
        cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        connection.execute("DELETE FROM document_grants WHERE document_id = ?", (document_id,))
        return cursor.rowcount > 0


def accessible_document_ids(owner: str) -> set[str]:
    rows = database.query(
        """
        SELECT d.id FROM documents d
        WHERE d.owner_id = ?
           OR d.id IN (SELECT document_id FROM document_grants WHERE user_id = ?)
        """,
        (owner, owner),
    )
    return {row["id"] for row in rows}


def owns_document(owner: str, document_id: str) -> bool:
    row = database.query_one(
        "SELECT 1 AS ok FROM documents WHERE id = ? AND owner_id = ?",
        (document_id, owner),
    )
    return bool(row)


def grant_document(document_id: str, user_id: str, permission: str = "read") -> None:
    ensure_user(user_id)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO document_grants(document_id, user_id, permission, granted_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(document_id, user_id)
            DO UPDATE SET permission = excluded.permission
            """,
            (document_id, user_id, permission, utc_now()),
        )


def revoke_document(document_id: str, user_id: str) -> None:
    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM document_grants WHERE document_id = ? AND user_id = ?",
            (document_id, user_id),
        )


def document_grants(document_id: str) -> list[dict[str, Any]]:
    rows = database.query(
        "SELECT * FROM document_grants WHERE document_id = ? ORDER BY granted_at",
        (document_id,),
    )
    return [dict(row) for row in rows]


def count_documents() -> int:
    row = database.query_one("SELECT COUNT(*) AS c FROM documents")
    return int(row["c"]) if row else 0


# ---------------------------------------------------------------------------
# Host policy
# ---------------------------------------------------------------------------
def load_policy(defaults: dict[str, Any]) -> dict[str, Any]:
    row = database.query_one(
        "SELECT * FROM host_policies WHERE id = ?", (DEFAULT_POLICY_ID,)
    )
    if row:
        return policy_from_row(row)
    stored = {
        **defaults,
        "updated_at": None,
        "updated_by": None,
    }
    save_policy_record(stored)
    return stored


def save_policy_record(policy: dict[str, Any]) -> dict[str, Any]:
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO host_policies(
                id, org_purpose, allowed_topics_json, restricted_topics_json,
                document_access, screen_analysis, external_voice, system_rules,
                max_context_chunks, updated_at, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                org_purpose = excluded.org_purpose,
                allowed_topics_json = excluded.allowed_topics_json,
                restricted_topics_json = excluded.restricted_topics_json,
                document_access = excluded.document_access,
                screen_analysis = excluded.screen_analysis,
                external_voice = excluded.external_voice,
                system_rules = excluded.system_rules,
                max_context_chunks = excluded.max_context_chunks,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (
                DEFAULT_POLICY_ID,
                policy["org_purpose"],
                dumps(policy.get("allowed_topics", [])),
                dumps(policy.get("restricted_topics", [])),
                1 if policy.get("document_access") else 0,
                1 if policy.get("screen_analysis") else 0,
                1 if policy.get("external_voice") else 0,
                policy.get("system_rules", ""),
                int(policy.get("max_context_chunks") or 4),
                policy.get("updated_at") or utc_now(),
                policy.get("updated_by") or "admin",
            ),
        )
    return policy


# ---------------------------------------------------------------------------
# Application settings and model selection
# ---------------------------------------------------------------------------
MODEL_SETTING_KEYS = {
    "chat": "models.chat_model",
    "embedding": "models.embedding_model",
    "vision": "models.vision_model",
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "chat_history_limit": 12,
    "document_top_k": settings.top_k,
}


def get_setting(key: str, default: Any = None) -> Any:
    row = database.query_one("SELECT value_json FROM app_settings WHERE key = ?", (key,))
    if not row:
        return default
    return loads(row["value_json"], default)


def set_setting(key: str, value: Any, updated_by: str = "admin") -> Any:
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO app_settings(key, value_json, updated_at, updated_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
            """,
            (key, dumps(value), utc_now(), updated_by),
        )
    return value


def all_settings() -> dict[str, Any]:
    """Preferences plus model selections, with effective defaults applied."""
    preferences = dict(DEFAULT_SETTINGS)
    for key, default in DEFAULT_SETTINGS.items():
        preferences[key] = get_setting(key, default)
    return {**preferences, **selected_models()}


def selected_models() -> dict[str, Any]:
    return {
        "chat_model": get_setting(MODEL_SETTING_KEYS["chat"], settings.default_model),
        "embedding_model": get_setting(
            MODEL_SETTING_KEYS["embedding"], settings.embedding_model
        ),
        "vision_model": get_setting(MODEL_SETTING_KEYS["vision"], settings.vision_model),
        "updated_at": get_setting("models.updated_at", None),
        "updated_by": get_setting("models.updated_by", None),
    }


def set_selected_model(kind: str, name: str, updated_by: str = "admin") -> dict[str, Any]:
    key = MODEL_SETTING_KEYS[kind]
    set_setting(key, name, updated_by)
    set_setting("models.updated_at", utc_now(), updated_by)
    set_setting("models.updated_by", updated_by, updated_by)
    return selected_models()


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def record_audit(
    actor: str,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    try:
        database.execute(
            """
            INSERT INTO audit_logs(actor, action, target_type, target_id, detail_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                actor or "system",
                action,
                target_type,
                target_id,
                dumps(detail) if detail else None,
                utc_now(),
            ),
        )
    except Exception as exc:  # pragma: no cover - audit must never break a request
        logger.warning("Could not write audit record for %s: %s", action, exc)


def list_audit(limit: int = 200) -> list[dict[str, Any]]:
    rows = database.query(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)
    )
    items = []
    for row in rows:
        item = dict(row)
        item["detail"] = loads(item.pop("detail_json", None), None)
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Client presence
# ---------------------------------------------------------------------------
ACTIVE_WINDOW_SECONDS = 90


def heartbeat_client(client_id: str, name: str, mode: str) -> int:
    ensure_user(client_id)
    now = utc_now()
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT client_id FROM client_presence WHERE client_id = ?", (client_id,)
        ).fetchone()
        if row:
            connection.execute(
                "UPDATE client_presence SET name = ?, mode = ?, last_seen = ? WHERE client_id = ?",
                (name, mode, now, client_id),
            )
        else:
            connection.execute(
                """
                INSERT INTO client_presence(client_id, name, mode, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                """,
                (client_id, name, mode, now, now),
            )
        connection.execute("DELETE FROM client_presence WHERE last_seen < ?", (_cutoff(),))
    return count_active_clients()


def _cutoff() -> str:
    return (
        datetime.now(timezone.utc) - timedelta(seconds=ACTIVE_WINDOW_SECONDS)
    ).isoformat(timespec="milliseconds")


def active_clients() -> list[dict[str, Any]]:
    rows = database.query(
        "SELECT * FROM client_presence WHERE last_seen >= ? ORDER BY last_seen DESC",
        (_cutoff(),),
    )
    return [dict(row) for row in rows]


def count_active_clients() -> int:
    return len(active_clients())


# ---------------------------------------------------------------------------
# Aggregate health helpers
# ---------------------------------------------------------------------------
def database_info() -> dict[str, Any]:
    info = database.info()
    info.update(
        {
            "counts": {
                "users": count_users(),
                "personas": count_personas(),
                "conversations": count_conversations(),
                "documents": count_documents(),
            }
        }
    )
    return info


# Kept for code that still imports these names.
def get_active_model() -> str:
    return selected_models()["chat_model"]


def set_active_model(model: str) -> str:
    set_selected_model("chat", model)
    return model
