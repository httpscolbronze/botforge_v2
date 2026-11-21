"""Automatic Ollama model discovery and selection status.

The registry asks the local Ollama server (``GET /api/tags``) which models are
installed, classifies them as chat / embedding / vision, and compares that list
with the selections persisted in SQLite.

Nothing here ever switches a selection on its own: a missing model is reported
to the host with the available alternatives, and inference refuses rather than
silently using a different model.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config import settings
from backend.engine.ollama_client import OllamaError, ollama
from backend.storage import repositories

logger = logging.getLogger("botforge.models")

EMBEDDING_HINTS = ("embed", "bge", "minilm", "e5-", "gte-", "snowflake-arctic-embed")
VISION_HINTS = ("llava", "vision", "moondream", "bakllava", "minicpm-v")
ROLE_LABELS = {"chat": "chat", "embedding": "embedding", "vision": "vision"}


def matches(installed_names: list[str], wanted: str) -> bool:
    """Treat ``llama3.2`` and ``llama3.2:latest`` as the same model."""
    if not wanted:
        return False
    if wanted in installed_names:
        return True
    base = wanted.split(":")[0]
    return any(
        name.split(":")[0] == base and (":" not in wanted or name.endswith(":latest"))
        for name in installed_names
    )


def classify(name: str) -> str:
    lowered = (name or "").lower()
    if any(hint in lowered for hint in EMBEDDING_HINTS):
        return "embedding"
    if any(hint in lowered for hint in VISION_HINTS):
        return "vision"
    return "chat"


class ModelRegistry:
    def __init__(self) -> None:
        self._state: dict[str, Any] = {
            "connected": False,
            "base_url": settings.ollama_base_url,
            "version": None,
            "models": [],
            "chat_models": [],
            "embedding_models": [],
            "vision_models": [],
            "error": "Model discovery has not run yet.",
            "discovered_at": None,
            "last_success_at": None,
            "selected": repositories.selected_models(),
            "missing": [],
            "warning": None,
        }

    # -- discovery ---------------------------------------------------------
    async def refresh(self) -> dict[str, Any]:
        health = await ollama.health()
        selected = repositories.selected_models()
        self._state.update(
            {
                "connected": bool(health.get("connected")),
                "base_url": settings.ollama_base_url,
                "version": health.get("version"),
                "selected": selected,
            }
        )
        if not health.get("connected"):
            self._state.update(
                {
                    "models": [],
                    "chat_models": [],
                    "embedding_models": [],
                    "vision_models": [],
                    "missing": [],
                    "warning": None,
                    "error": health.get("error")
                    or f"Ollama is not reachable at {settings.ollama_base_url}.",
                    "discovered_at": repositories.utc_now(),
                }
            )
            logger.warning("Model discovery failed: %s", self._state["error"])
            return self.snapshot()

        try:
            models = await ollama.list_models()
        except OllamaError as exc:
            self._state.update(
                {
                    "connected": True,
                    "models": [],
                    "chat_models": [],
                    "embedding_models": [],
                    "vision_models": [],
                    "missing": [],
                    "warning": None,
                    "error": exc.message,
                    "discovered_at": repositories.utc_now(),
                }
            )
            logger.warning("Model discovery failed: %s", exc.message)
            return self.snapshot()

        enriched = []
        for model in models:
            item = dict(model)
            item["kind"] = classify(item.get("name") or "")
            item["available"] = True
            enriched.append(item)

        names = [item["name"] for item in enriched]
        by_kind = {
            kind: [item["name"] for item in enriched if item["kind"] == kind]
            for kind in ("chat", "embedding", "vision")
        }

        missing: list[dict[str, Any]] = []
        for kind in ("chat", "embedding", "vision"):
            configured = selected.get(f"{kind}_model")
            if configured and not matches(names, configured):
                missing.append(
                    {
                        "role": kind,
                        "label": ROLE_LABELS[kind],
                        "model": configured,
                        "alternatives": by_kind[kind],
                    }
                )

        warning = None
        if missing:
            primary = next((item for item in missing if item["role"] == "chat"), missing[0])
            alternatives = ", ".join(primary["alternatives"][:5]) or "none installed"
            warning = (
                f"The selected {primary['label']} model '{primary['model']}' is not installed "
                f"in Ollama. Choose another model in Host Mode -> Models. "
                f"Available {primary['label']} models: {alternatives}."
            )
            logger.warning(warning)

        now = repositories.utc_now()
        self._state.update(
            {
                "models": enriched,
                "chat_models": by_kind["chat"],
                "embedding_models": by_kind["embedding"],
                "vision_models": by_kind["vision"],
                "missing": missing,
                "warning": warning,
                "error": None,
                "discovered_at": now,
                "last_success_at": now,
            }
        )
        logger.info(
            "Discovered %s Ollama models (%s chat, %s embedding, %s vision)",
            len(enriched),
            len(by_kind["chat"]),
            len(by_kind["embedding"]),
            len(by_kind["vision"]),
        )
        return self.snapshot()

    async def probe_connection(self) -> dict[str, Any]:
        """Cheap live check so offline state is reported without a full rescan."""
        health = await ollama.health()
        if not health.get("connected"):
            self._state.update(
                {
                    "connected": False,
                    "models": [],
                    "chat_models": [],
                    "embedding_models": [],
                    "vision_models": [],
                    "missing": [],
                    "warning": None,
                    "error": health.get("error")
                    or f"Ollama is not reachable at {settings.ollama_base_url}.",
                }
            )
            return self.snapshot()
        if not self._state["connected"] or not self._state["last_success_at"]:
            return await self.refresh()
        return self.snapshot()

    # -- reads -------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        state = dict(self._state)
        state["selected"] = repositories.selected_models()
        return state

    def status(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            "connected": snapshot["connected"],
            "base_url": snapshot["base_url"],
            "version": snapshot["version"],
            "error": snapshot["error"],
            "discovered_at": snapshot["discovered_at"],
            "last_success_at": snapshot["last_success_at"],
            "counts": {
                "total": len(snapshot["models"]),
                "chat": len(snapshot["chat_models"]),
                "embedding": len(snapshot["embedding_models"]),
                "vision": len(snapshot["vision_models"]),
            },
            "selected": self.selected_status(),
            "missing": snapshot["missing"],
            "warning": snapshot["warning"],
        }

    def selected_status(self) -> dict[str, Any]:
        selected = repositories.selected_models()
        known = bool(self._state["models"]) and self._state["connected"]
        names = [model["name"] for model in self._state["models"]]
        availability = {
            kind: (matches(names, selected.get(f"{kind}_model") or "") if known else None)
            for kind in ("chat", "embedding", "vision")
        }
        return {
            **selected,
            "chat_available": availability["chat"],
            "embedding_available": availability["embedding"],
            "vision_available": availability["vision"],
            "availability_known": known,
        }

    def available(self, name: str) -> bool | None:
        """True/False when discovery has run, None when Ollama is offline."""
        if not name:
            return False
        if not self._state["connected"] or not self._state["models"]:
            return None
        return matches([model["name"] for model in self._state["models"]], name)

    def chat_alternatives(self) -> list[str]:
        return list(self._state["chat_models"])

    def reset(self) -> None:
        self._state.update(
            {
                "connected": False,
                "models": [],
                "chat_models": [],
                "embedding_models": [],
                "vision_models": [],
                "missing": [],
                "warning": None,
                "error": "Model discovery has not run yet.",
            }
        )


model_registry = ModelRegistry()
