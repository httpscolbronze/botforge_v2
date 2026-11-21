"""Streaming chat with policy enforcement, personas, agents and RAG context.

Conversations and messages are persisted in SQLite as they happen. The chat
model comes from the agent configuration when one is set, otherwise from the
host-selected default. A configured model that is no longer installed is
reported to the user instead of being silently replaced.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.engine.model_registry import model_registry
from backend.engine.ollama_client import OllamaError, ollama
from backend.engine.persona import DEFAULT_PERSONA, build_system_prompt, normalise_persona
from backend.engine.policy_engine import get_policy, preflight_check
from backend.rag.embeddings import EmbeddingUnavailable, embed_query
from backend.rag.retrieval import build_context, vector_store
from backend.routes.deps import client_id
from backend.storage import repositories

logger = logging.getLogger("botforge.chat")
router = APIRouter(tags=["chat"])

DEFAULT_HISTORY_LIMIT = 12


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=64)
    persona: dict[str, Any] | None = None
    persona_id: str | None = Field(default=None, max_length=64)
    use_documents: bool = True
    document_ids: list[str] | None = None
    history: list[ChatTurn] | None = Field(default=None, max_length=40)
    stream: bool = True


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _history_limit() -> int:
    try:
        value = int(repositories.get_setting("chat_history_limit", DEFAULT_HISTORY_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_HISTORY_LIMIT
    return max(1, min(value, 40))


def _resolve_persona(payload: ChatRequest, client: str) -> dict[str, Any]:
    stored = repositories.list_personas(client)
    match: dict[str, Any] | None = None
    if payload.persona_id:
        match = next((p for p in stored if p["id"] == payload.persona_id), None)
    if match is None and payload.persona:
        persona = normalise_persona(payload.persona)
        persona["chat_model"] = payload.persona.get("chat_model")
        persona["id"] = payload.persona_id or payload.persona.get("id")
        return persona
    if match is None and stored:
        match = stored[0]
    if match is None:
        persona = normalise_persona(DEFAULT_PERSONA)
        persona["chat_model"] = None
        return persona
    persona = normalise_persona(match)
    persona["id"] = match["id"]
    persona["chat_model"] = match.get("chat_model")
    return persona


def _resolve_chat_model(client: str, persona: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Agent model wins; otherwise the host default. Never silently switch."""
    configured = None
    agent = None
    if persona.get("id"):
        agent = repositories.get_agent_for_persona(client, persona["id"])
        if agent:
            configured = agent.get("chat_model")
    configured = configured or persona.get("chat_model")

    if configured:
        available = model_registry.available(configured)
        if available is False:
            alternatives = ", ".join(model_registry.chat_alternatives()[:6]) or "none installed"
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This agent is configured to use '{configured}', which is not installed in "
                    f"Ollama. Ask the host to pull it or pick another model in Host Mode -> "
                    f"Models. Available chat models: {alternatives}."
                ),
            )
        return configured, agent

    selected = repositories.selected_models()["chat_model"]
    if model_registry.available(selected) is False:
        alternatives = ", ".join(model_registry.chat_alternatives()[:6]) or "none installed"
        raise HTTPException(
            status_code=409,
            detail=(
                f"The host-selected chat model '{selected}' is not installed in Ollama. "
                f"Pull it or choose another model in Host Mode -> Models. "
                f"Available chat models: {alternatives}."
            ),
        )
    return selected, agent


def _allowed_document_ids(client: str, requested: list[str] | None) -> list[str]:
    own = repositories.accessible_document_ids(client)
    if requested:
        return [doc_id for doc_id in requested if doc_id in own]
    return list(own)


async def _retrieve_context(
    message: str, client: str, payload: ChatRequest, policy: dict[str, Any]
) -> tuple[str, list[dict[str, Any]], str | None, str | None]:
    """Return (context_block, sources, embedding_provider, warning)."""
    if not payload.use_documents or not policy["document_access"]:
        return "", [], None, None
    doc_ids = _allowed_document_ids(client, payload.document_ids)
    if not doc_ids:
        return "", [], None, None

    try:
        embedding = await embed_query(message)
    except EmbeddingUnavailable as exc:
        logger.warning("Skipping retrieval: %s", exc)
        return "", [], None, str(exc)

    default_k = int(repositories.get_setting("document_top_k", policy["max_context_chunks"]))
    k = max(1, min(default_k, policy["max_context_chunks"], 12))
    hits = await asyncio.to_thread(
        vector_store.query, embedding["vectors"][0], document_ids=doc_ids, k=k
    )
    hits = [hit for hit in hits if hit.get("text") and hit.get("score", 0) > 0]
    sources = []
    seen = set()
    for hit in hits:
        key = (hit.get("document_id"), hit.get("page"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "document_id": hit.get("document_id"),
                "document_name": hit.get("document_name"),
                "page": hit.get("page"),
                "score": hit.get("score"),
                "preview": (hit.get("text") or "")[:240],
            }
        )
    return build_context(hits), sources, embedding["provider"], embedding["warning"]


def _build_messages(
    policy: dict[str, Any],
    persona: dict[str, Any],
    history: list[dict[str, Any]],
    message: str,
    context: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(policy, persona)}
    ]
    for turn in history[-_history_limit():]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    user_content = message
    if context:
        user_content = (
            f"{context}\n\n"
            "# User question\n"
            f"{message}\n\n"
            "Answer using the excerpts when they are relevant and cite them as "
            "Source 1, Source 2, etc. If they do not contain the answer, say so plainly."
        )
    messages.append({"role": "user", "content": user_content})
    return messages


@router.post("/chat")
async def chat(payload: ChatRequest, client: str = Depends(client_id)):
    policy = get_policy()

    refusal = preflight_check(payload.message, policy)
    if refusal:
        raise HTTPException(status_code=403, detail=refusal)

    conversation = None
    if payload.conversation_id:
        conversation = repositories.get_conversation(client, payload.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found in this workspace.")

    if conversation:
        history = [
            {"role": message["role"], "content": message["content"]}
            for message in conversation.get("messages", [])
        ]
    else:
        history = [
            {"role": turn.role, "content": turn.content}
            for turn in (payload.history or [])
        ]

    persona = _resolve_persona(payload, client)
    model, agent = _resolve_chat_model(client, persona)
    context, sources, embedding_provider, embedding_warning = await _retrieve_context(
        payload.message, client, payload, policy
    )
    messages = _build_messages(policy, persona, history, payload.message, context)

    if conversation is None:
        title = payload.message.strip().replace("\n", " ")[:70]
        conversation = repositories.create_conversation(
            client,
            title=title or "New conversation",
            model=model,
            persona_id=persona.get("id") if isinstance(persona.get("id"), str) else None,
            agent_id=agent["id"] if agent else None,
        )

    conversation_id = conversation["id"]
    repositories.add_message(conversation_id, "user", payload.message, model=model)

    meta = {
        "type": "meta",
        "conversation_id": conversation_id,
        "model": model,
        "persona_name": persona.get("name"),
        "agent_id": agent["id"] if agent else None,
        "sources": sources,
        "embedding_provider": embedding_provider,
        "warning": embedding_warning,
        "policy_enforced": True,
    }

    if not payload.stream:
        try:
            reply = await ollama.chat(model, messages)
        except OllamaError as exc:
            logger.error("Chat failed: %s", exc.message)
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
        repositories.add_message(
            conversation_id, "assistant", reply, sources=sources or None, model=model
        )
        repositories.record_audit(
            client,
            "chat.completed",
            target_type="conversation",
            target_id=conversation_id,
            detail={"model": model, "sources": len(sources)},
        )
        logger.info("Chat answered with %s (%s sources)", model, len(sources))
        return {
            "conversation_id": conversation_id,
            "reply": reply,
            "model": model,
            "sources": sources,
            "embedding_provider": embedding_provider,
            "warning": embedding_warning,
            "policy_enforced": True,
        }

    async def event_stream() -> AsyncIterator[str]:
        yield _sse(meta)
        collected: list[str] = []
        try:
            async for token in ollama.chat_stream(model, messages):
                collected.append(token)
                yield _sse({"type": "token", "content": token})
        except OllamaError as exc:
            logger.error("Stream failed: %s", exc.message)
            yield _sse({"type": "error", "message": exc.message})
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected streaming error")
            yield _sse({"type": "error", "message": f"Streaming failed: {exc}"})
            return

        answer = "".join(collected).strip()
        if not answer:
            yield _sse(
                {
                    "type": "error",
                    "message": "The model returned an empty answer. Try rephrasing your question.",
                }
            )
            return
        repositories.add_message(
            conversation_id, "assistant", answer, sources=sources or None, model=model
        )
        repositories.record_audit(
            client,
            "chat.completed",
            target_type="conversation",
            target_id=conversation_id,
            detail={"model": model, "sources": len(sources), "streamed": True},
        )
        logger.info("Chat streamed with %s (%s sources)", model, len(sources))
        yield _sse(
            {
                "type": "done",
                "content": answer,
                "conversation_id": conversation_id,
                "sources": sources,
                "model": model,
            }
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
async def list_conversations(client: str = Depends(client_id)) -> dict:
    return {"conversations": repositories.conversation_summaries(client)}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, client: str = Depends(client_id)) -> dict:
    conversation = repositories.get_conversation(client, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"conversation": conversation}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, client: str = Depends(client_id)) -> dict:
    if not repositories.delete_conversation(client, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    repositories.record_audit(
        client, "conversation.delete", target_type="conversation", target_id=conversation_id
    )
    return {"deleted": conversation_id}
