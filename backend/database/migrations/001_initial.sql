-- BotForge_v2 initial schema.
-- Applied once by backend.database.connection.Database.initialize().

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'client'
                  CHECK (role IN ('admin', 'client', 'agent')),
    password_hash TEXT,
    created_at    TEXT NOT NULL,
    last_seen_at  TEXT
);

CREATE TABLE IF NOT EXISTS personas (
    id                      TEXT PRIMARY KEY,
    owner_id                TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                    TEXT NOT NULL,
    role                    TEXT NOT NULL DEFAULT '',
    tone                    TEXT NOT NULL DEFAULT '',
    response_style          TEXT NOT NULL DEFAULT '',
    expertise               TEXT NOT NULL DEFAULT '',
    language                TEXT NOT NULL DEFAULT '',
    additional_instructions TEXT NOT NULL DEFAULT '',
    is_default              INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_personas_owner ON personas(owner_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persona_id      TEXT REFERENCES personas(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    chat_model      TEXT,
    embedding_model TEXT,
    config_json     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agents_owner ON agents(owner_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agents_persona ON agents(persona_id);

CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    owner_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id   TEXT REFERENCES agents(id) ON DELETE SET NULL,
    persona_id TEXT REFERENCES personas(id) ON DELETE SET NULL,
    title      TEXT NOT NULL,
    model      TEXT,
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_owner
    ON conversations(owner_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    sources_json    TEXT,
    model           TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS host_policies (
    id                  TEXT PRIMARY KEY,
    org_purpose         TEXT NOT NULL,
    allowed_topics_json TEXT NOT NULL DEFAULT '[]',
    restricted_topics_json TEXT NOT NULL DEFAULT '[]',
    document_access     INTEGER NOT NULL DEFAULT 1,
    screen_analysis     INTEGER NOT NULL DEFAULT 1,
    external_voice      INTEGER NOT NULL DEFAULT 1,
    system_rules        TEXT NOT NULL DEFAULT '',
    max_context_chunks  INTEGER NOT NULL DEFAULT 4,
    updated_at          TEXT,
    updated_by          TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id                 TEXT PRIMARY KEY,
    owner_id           TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    extension          TEXT NOT NULL,
    size_bytes         INTEGER NOT NULL DEFAULT 0,
    pages              INTEGER NOT NULL DEFAULT 0,
    chunks             INTEGER NOT NULL DEFAULT 0,
    embedding_provider TEXT,
    embedding_model    TEXT,
    stored_path        TEXT NOT NULL,
    checksum           TEXT,
    status             TEXT NOT NULL DEFAULT 'indexed',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS document_grants (
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission  TEXT NOT NULL DEFAULT 'read' CHECK (permission IN ('read', 'write')),
    granted_at  TEXT NOT NULL,
    PRIMARY KEY (document_id, user_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target_type TEXT,
    target_id   TEXT,
    detail_json TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS client_presence (
    client_id  TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    mode       TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);
