"""Runtime configuration for BotForge_v2.

Everything is environment driven so the same code works for a local install
and for a hosted demo. Secrets are only ever read here, never shipped to the
browser.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

try:  # optional dependency; the app runs fine without a .env file
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:  # pragma: no cover - dotenv is a convenience helper
    pass


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


class Settings:
    """Process-wide settings snapshot."""

    app_name = "BotForge_v2"
    version = "2.1.0"

    # Local API
    host = _env("BOTFORGE_HOST", "127.0.0.1")
    port = _env_int("BOTFORGE_PORT", 8000)
    data_dir = Path(_env("BOTFORGE_DATA_DIR", str(BASE_DIR / "data"))).expanduser()
    cors_origins = [
        origin.strip()
        for origin in _env(
            "BOTFORGE_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    # Ollama. These are *defaults* only: the host can pick different models in
    # Host Mode and the selection is persisted in SQLite.
    ollama_base_url = _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    default_model = _env("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
    embedding_model = _env("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    vision_model = _env("OLLAMA_VISION_MODEL", "llava")
    embedding_fallback = _env_bool("BOTFORGE_EMBEDDING_FALLBACK", True)

    # Host mode / admin
    admin_password = _env("BOTFORGE_ADMIN_PASSWORD", "botforge-admin")
    session_secret = _env("BOTFORGE_SESSION_SECRET", "dev-insecure-secret-change-me")
    session_ttl_minutes = _env_int("BOTFORGE_SESSION_TTL_MINUTES", 720)

    # ElevenLabs (optional)
    elevenlabs_api_key = _env("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id = _env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    elevenlabs_model_id = _env("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    # RAG tuning
    chunk_size = max(200, _env_int("BOTFORGE_CHUNK_SIZE", 900))
    chunk_overlap = max(0, _env_int("BOTFORGE_CHUNK_OVERLAP", 150))
    top_k = max(1, _env_int("BOTFORGE_TOP_K", 4))
    max_upload_mb = max(1, _env_int("BOTFORGE_MAX_UPLOAD_MB", 25))

    # -- persistent storage paths -----------------------------------------
    @property
    def db_path(self) -> Path:
        return self.data_dir / "botforge.db"

    @property
    def documents_dir(self) -> Path:
        """Original uploaded files. Metadata lives in SQLite."""
        return self.data_dir / "documents"

    @property
    def uploads_dir(self) -> Path:
        """Legacy upload location kept readable for existing installs."""
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma_db"

    @property
    def conversations_dir(self) -> Path:
        return self.data_dir / "conversations"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def using_default_password(self) -> bool:
        return self.admin_password == "botforge-admin"

    @property
    def using_default_session_secret(self) -> bool:
        return self.session_secret == "dev-insecure-secret-change-me"

    def storage_dirs(self) -> tuple[Path, ...]:
        return (
            self.data_dir,
            self.documents_dir,
            self.uploads_dir,
            self.chroma_dir,
            self.conversations_dir,
            self.logs_dir,
            self.backups_dir,
        )

    def ensure_dirs(self) -> None:
        for path in self.storage_dirs():
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
