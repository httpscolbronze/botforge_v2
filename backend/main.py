"""BotForge_v2 API entrypoint.

Run locally (loopback only):
    uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

Startup order: create data directories, open/migrate SQLite, seed the admin
user, attach the persistent ChromaDB collection, then discover Ollama models.
Nothing in this path deletes user data.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import PROJECT_ROOT, settings
from backend.database.connection import database
from backend.engine.model_registry import model_registry
from backend.engine.policy_engine import get_policy
from backend.log_buffer import install_logging
from backend.rag.retrieval import vector_store
from backend.routes import (
    auth,
    chat,
    clients,
    documents,
    models,
    personas,
    policies,
    screen,
    settings as settings_routes,
    system,
    voice,
)
from backend.storage import repositories
from backend.storage.repositories import utc_now

logger = logging.getLogger("botforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    install_logging()

    try:
        database.initialize()
        repositories.ensure_admin_user()
        logger.info(
            "SQLite ready at %s (%s migrations applied)",
            settings.db_path,
            len(database.migrations()),
        )
    except Exception as exc:  # pragma: no cover - startup failure must be visible
        logger.exception("Database initialisation failed")
        raise RuntimeError(
            f"BotForge could not open its database at {settings.db_path}: {exc}"
        ) from exc

    logger.info("BotForge_v2 starting (API %s:%s)", settings.host, settings.port)
    if settings.using_default_password:
        logger.warning(
            "Host Mode is using the default admin password. Set BOTFORGE_ADMIN_PASSWORD in .env."
        )
    if settings.using_default_session_secret:
        logger.warning("Using the default session secret. Set BOTFORGE_SESSION_SECRET in .env.")

    selected = repositories.selected_models()
    logger.info(
        "Selected models: chat=%s embedding=%s vision=%s",
        selected["chat_model"],
        selected["embedding_model"],
        selected["vision_model"],
    )

    # Persistent vector collection (never reset on startup).
    stats = await asyncio.to_thread(vector_store.stats)
    logger.info("Vector store backend=%s chunks=%s", stats.get("backend"), stats.get("chunks"))

    # Automatic model discovery; failures are logged, not fatal.
    status = await model_registry.refresh()
    if status.get("connected"):
        logger.info(
            "Ollama reachable (version %s): %s models discovered",
            status.get("version"),
            len(status.get("models", [])),
        )
    else:
        logger.warning(status.get("error") or "Ollama is not reachable")

    repositories.record_audit(
        "system",
        "app.start",
        detail={
            "version": settings.version,
            "ollama_connected": status.get("connected"),
            "models": len(status.get("models", [])),
        },
    )
    yield
    repositories.record_audit("system", "app.stop")
    logger.info("BotForge_v2 stopped")


app = FastAPI(
    title="BotForge_v2",
    version=settings.version,
    description="Local-first AI agent platform. Inference, documents and data stay on the host.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Client-Id"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith(
        ("/chat", "/documents", "/screen", "/voice", "/conversations", "/settings")
    ):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "The BotForge backend hit an internal error. Check the Host Mode logs for details."
        },
    )


@app.get("/health", tags=["system"])
async def health() -> dict:
    policy = get_policy()
    database_info = repositories.database_info()
    selected = repositories.selected_models()
    await model_registry.probe_connection()
    model_status = model_registry.status()
    warnings = [
        warning
        for warning in [
            "Host Mode is using the default admin password (botforge-admin)."
            if settings.using_default_password
            else None,
            model_status.get("warning"),
            model_status.get("error") if not model_status.get("connected") else None,
        ]
        if warning
    ]
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "time": utc_now(),
        "api": {"host": settings.host, "port": settings.port},
        "ollama": {
            "connected": model_status["connected"],
            "base_url": settings.ollama_base_url,
            "version": model_status.get("version"),
            "error": model_status.get("error"),
        },
        "active_model": selected["chat_model"],
        "default_model": settings.default_model,
        "embedding_model": selected["embedding_model"],
        "models": {
            "selected": selected,
            "available": model_status["selected"]["chat_available"],
            "installed": model_status["counts"]["total"],
            "missing": model_status.get("missing", []),
            "warning": model_status.get("warning"),
            "discovered_at": model_status.get("discovered_at"),
        },
        "database": {
            "engine": database_info["engine"],
            "path": database_info["path"],
            "size_bytes": database_info["size_bytes"],
            "migrations": [item["version"] for item in database_info["migrations"]],
            "counts": database_info["counts"],
        },
        "documents": {
            "count": database_info["counts"]["documents"],
            "access_enabled": policy["document_access"],
        },
        "personas": database_info["counts"]["personas"],
        "conversations": database_info["counts"]["conversations"],
        "vector_store": vector_store.stats(),
        "voice": {
            "provider": "elevenlabs",
            "configured": bool(settings.elevenlabs_api_key),
            "enabled_by_policy": policy["external_voice"],
            "external": True,
        },
        "warnings": warnings,
    }


for module in (
    auth,
    models,
    settings_routes,
    policies,
    personas,
    documents,
    chat,
    screen,
    voice,
    clients,
    system,
):
    app.include_router(module.router)


# Serve the built frontend when it exists (production preview / Render).
DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
if (DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")
    logger.info("Serving built frontend from %s", DIST_DIR)
else:

    @app.get("/", tags=["system"])
    async def api_root() -> dict:
        return {
            "app": settings.app_name,
            "version": settings.version,
            "mode": "api-only",
            "docs": "/docs",
            "hint": "Run the Vite dev server in frontend/ (npm run dev) for the UI.",
        }
