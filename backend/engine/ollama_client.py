"""Async Ollama client.

Every failure mode is turned into a clear, user-facing error instead of a fake
answer: if Ollama is down or a model is missing, the API says so.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from backend.config import settings

logger = logging.getLogger("botforge.ollama")


class OllamaError(Exception):
    """Raised for any Ollama problem; message is safe to show to the user."""

    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _friendly_connect_error(base_url: str) -> str:
    return (
        f"Ollama is not reachable at {base_url}. Start it with `ollama serve` "
        f"and make sure the URL matches OLLAMA_BASE_URL."
    )


class OllamaClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")

    def _client(self, read_timeout: float = 600.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(connect=4.0, read=read_timeout, write=60.0, pool=10.0),
        )

    # -- health & models ---------------------------------------------------
    async def health(self) -> dict[str, Any]:
        try:
            async with self._client(read_timeout=8.0) as client:
                response = await client.get("/api/version")
                response.raise_for_status()
                payload = response.json()
            return {
                "connected": True,
                "base_url": self.base_url,
                "version": payload.get("version"),
            }
        except httpx.ConnectError:
            return {
                "connected": False,
                "base_url": self.base_url,
                "error": _friendly_connect_error(self.base_url),
            }
        except httpx.TimeoutException:
            return {
                "connected": False,
                "base_url": self.base_url,
                "error": f"Ollama at {self.base_url} did not respond in time.",
            }
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "connected": False,
                "base_url": self.base_url,
                "error": f"Ollama health check failed: {exc}",
            }

    async def list_models(self) -> list[dict[str, Any]]:
        try:
            async with self._client(read_timeout=15.0) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                payload = response.json()
        except httpx.ConnectError as exc:
            raise OllamaError(_friendly_connect_error(self.base_url)) from exc
        except httpx.TimeoutException as exc:
            raise OllamaError(f"Ollama at {self.base_url} timed out listing models.") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaError(f"Ollama returned HTTP {exc.response.status_code} listing models.") from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise OllamaError(f"Could not list Ollama models: {exc}") from exc

        models = []
        for item in payload.get("models", []):
            details = item.get("details") or {}
            models.append(
                {
                    "name": item.get("name") or item.get("model"),
                    "size": item.get("size"),
                    "modified_at": item.get("modified_at"),
                    "family": details.get("family"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization_level": details.get("quantization_level"),
                }
            )
        models.sort(key=lambda m: (m.get("name") or "").lower())
        return models

    async def running_models(self) -> list[dict[str, Any]]:
        try:
            async with self._client(read_timeout=10.0) as client:
                response = await client.get("/api/ps")
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []
        result = []
        for item in payload.get("models", []):
            result.append(
                {
                    "name": item.get("name") or item.get("model"),
                    "size": item.get("size"),
                    "size_vram": item.get("size_vram"),
                    "expires_at": item.get("expires_at"),
                }
            )
        return result

    async def pull_model(self, name: str) -> AsyncIterator[dict[str, Any]]:
        """Stream pull progress events as dicts."""
        try:
            async with self._client(read_timeout=None) as client:
                async with client.stream(
                    "POST", "/api/pull", json={"name": name, "stream": True}
                ) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode(errors="ignore")
                        raise OllamaError(
                            f"Ollama refused to pull '{name}' (HTTP {response.status_code}): {body[:300]}"
                        )
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        except OllamaError:
            raise
        except httpx.ConnectError as exc:
            raise OllamaError(_friendly_connect_error(self.base_url)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise OllamaError(f"Model pull failed: {exc}") from exc

    async def load_model(self, name: str, keep_alive: str = "10m") -> dict[str, Any]:
        """Warm a model into memory (Ollama loads lazily on generate)."""
        try:
            async with self._client(read_timeout=300.0) as client:
                response = await client.post(
                    "/api/generate",
                    json={"model": name, "prompt": "", "keep_alive": keep_alive, "stream": False},
                )
                if response.status_code >= 400:
                    raise OllamaError(
                        f"Model '{name}' could not be loaded (HTTP {response.status_code}). "
                        f"Pull it first from Host Mode -> Models."
                    )
                return {"loaded": name, "keep_alive": keep_alive}
        except OllamaError:
            raise
        except httpx.ConnectError as exc:
            raise OllamaError(_friendly_connect_error(self.base_url)) from exc
        except Exception as exc:
            raise OllamaError(f"Could not load model '{name}': {exc}") from exc

    async def unload_model(self, name: str) -> dict[str, Any]:
        try:
            async with self._client(read_timeout=60.0) as client:
                response = await client.post(
                    "/api/generate",
                    json={"model": name, "prompt": "", "keep_alive": 0, "stream": False},
                )
                if response.status_code >= 400:
                    raise OllamaError(f"Model '{name}' could not be unloaded.")
                return {"unloaded": name}
        except OllamaError:
            raise
        except httpx.ConnectError as exc:
            raise OllamaError(_friendly_connect_error(self.base_url)) from exc
        except Exception as exc:
            raise OllamaError(f"Could not unload model '{name}': {exc}") from exc

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        images: list[str] | None = None,
        temperature: float = 0.7,
        num_ctx: int = 4096,
    ) -> str:
        """Non-streaming chat completion."""
        payload = {
            "model": model,
            "messages": self._with_images(messages, images),
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        try:
            async with self._client() as client:
                response = await client.post("/api/chat", json=payload)
                if response.status_code == 404:
                    raise OllamaError(
                        f"Model '{model}' is not installed in Ollama. "
                        f"Pull it from Host Mode -> Models (ollama pull {model})."
                    )
                if response.status_code >= 400:
                    raise OllamaError(
                        f"Ollama chat failed (HTTP {response.status_code}): {response.text[:300]}"
                    )
                data = response.json()
        except OllamaError:
            raise
        except httpx.ConnectError as exc:
            raise OllamaError(_friendly_connect_error(self.base_url)) from exc
        except httpx.ReadTimeout as exc:
            raise OllamaError(
                "Ollama took too long to answer. The model may be loading for the first time; "
                "try again once it is warm."
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise OllamaError(f"Ollama chat failed: {exc}") from exc

        content = (data.get("message") or {}).get("content", "")
        if not content.strip():
            raise OllamaError("Ollama returned an empty response. Try a shorter prompt.")
        return content

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        images: list[str] | None = None,
        temperature: float = 0.7,
        num_ctx: int = 4096,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": self._with_images(messages, images),
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        try:
            async with self._client() as client:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    if response.status_code == 404:
                        raise OllamaError(
                            f"Model '{model}' is not installed in Ollama. "
                            f"Pull it from Host Mode -> Models (ollama pull {model})."
                        )
                    if response.status_code >= 400:
                        body = (await response.aread()).decode(errors="ignore")
                        raise OllamaError(
                            f"Ollama chat failed (HTTP {response.status_code}): {body[:300]}"
                        )
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if chunk.get("error"):
                            raise OllamaError(f"Ollama error: {chunk['error']}")
                        piece = (chunk.get("message") or {}).get("content", "")
                        if piece:
                            yield piece
                        if chunk.get("done"):
                            break
        except OllamaError:
            raise
        except httpx.ConnectError as exc:
            raise OllamaError(_friendly_connect_error(self.base_url)) from exc
        except httpx.ReadTimeout as exc:
            raise OllamaError(
                "Ollama stopped responding mid-stream. The model may still be loading."
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise OllamaError(f"Ollama streaming failed: {exc}") from exc

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model = model or settings.embedding_model
        if not texts:
            return []
        payload = {"model": model, "input": texts}
        try:
            async with self._client(read_timeout=180.0) as client:
                response = await client.post("/api/embed", json=payload)
                if response.status_code == 404:
                    # Older Ollama builds only expose /api/embeddings (single input).
                    return await self._legacy_embed(client, texts, model)
                if response.status_code >= 400:
                    raise OllamaError(
                        f"Embedding model '{model}' is unavailable (HTTP {response.status_code}). "
                        f"Run `ollama pull {model}`."
                    )
                data = response.json()
            vectors = data.get("embeddings") or []
            if len(vectors) != len(texts):
                raise OllamaError(
                    f"Embedding model '{model}' returned an unexpected number of vectors."
                )
            return vectors
        except OllamaError:
            raise
        except httpx.ConnectError as exc:
            raise OllamaError(_friendly_connect_error(self.base_url)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise OllamaError(f"Embedding generation failed: {exc}") from exc

    async def _legacy_embed(
        self, client: httpx.AsyncClient, texts: list[str], model: str
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            response = await client.post(
                "/api/embeddings", json={"model": model, "prompt": text}
            )
            if response.status_code >= 400:
                raise OllamaError(
                    f"Embedding model '{model}' is unavailable (HTTP {response.status_code}). "
                    f"Run `ollama pull {model}`."
                )
            vectors.append(response.json().get("embedding") or [])
        return vectors

    @staticmethod
    def _with_images(
        messages: list[dict[str, Any]], images: list[str] | None
    ) -> list[dict[str, Any]]:
        if not images:
            return messages
        prepared = [dict(message) for message in messages]
        if not prepared:
            prepared = [{"role": "user", "content": ""}]
        last = prepared[-1]
        prepared[-1] = {
            "role": last.get("role", "user"),
            "content": last.get("content", ""),
            "images": images,
        }
        return prepared


ollama = OllamaClient()
