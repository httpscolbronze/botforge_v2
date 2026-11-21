"""Optional ElevenLabs text-to-speech.

This is the one feature that leaves the machine. It is off unless an API key is
configured, the host policy allows it, and the client explicitly asks for it.
The key never reaches the browser; audio is fetched server-side and streamed.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.config import settings
from backend.engine.policy_engine import get_policy

logger = logging.getLogger("botforge.voice")
router = APIRouter(tags=["voice"])

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice_id: str | None = Field(default=None, max_length=64)


@router.get("/voice/status")
async def voice_status() -> dict:
    policy = get_policy()
    return {
        "provider": "elevenlabs",
        "configured": bool(settings.elevenlabs_api_key),
        "enabled_by_policy": policy["external_voice"],
        "external": True,
        "note": (
            "Voice generation sends the selected text to ElevenLabs, an external service. "
            "Chat, documents and screen analysis stay local."
        ),
        **({"warning": "Set ELEVENLABS_API_KEY on the server to enable voice."}
           if not settings.elevenlabs_api_key else {}),
    }


@router.post("/voice/generate")
async def generate_voice(payload: VoiceRequest) -> Response:
    policy = get_policy()
    if not policy["external_voice"]:
        raise HTTPException(
            status_code=403,
            detail="External voice generation is disabled by the host AI policy.",
        )
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "ElevenLabs is not configured. Set ELEVENLABS_API_KEY in the server .env and "
                "restart the backend. Everything else in BotForge keeps working locally."
            ),
        )

    voice_id = (payload.voice_id or settings.elevenlabs_voice_id).strip()
    if not voice_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ElevenLabs voice id.")

    body = {
        "text": payload.text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            response = await client.post(
                f"{ELEVENLABS_URL}/{voice_id}", json=body, headers=headers
            )
    except httpx.HTTPError as exc:
        logger.error("ElevenLabs request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach ElevenLabs. Voice is an external service and needs internet access.",
        ) from exc

    if response.status_code == 401:
        raise HTTPException(
            status_code=502,
            detail="ElevenLabs rejected the API key. Update ELEVENLABS_API_KEY on the server.",
        )
    if response.status_code == 429:
        raise HTTPException(
            status_code=429, detail="ElevenLabs rate limit or quota reached. Try again later."
        )
    if response.status_code >= 400:
        message = response.text[:300]
        logger.error("ElevenLabs HTTP %s: %s", response.status_code, message)
        raise HTTPException(
            status_code=502, detail=f"ElevenLabs could not generate audio (HTTP {response.status_code})."
        )

    audio = response.content
    if not audio:
        raise HTTPException(status_code=502, detail="ElevenLabs returned empty audio.")

    logger.info("Generated %s bytes of audio through ElevenLabs (external)", len(audio))
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Voice-Provider": "ElevenLabs (external)",
            "Content-Disposition": 'inline; filename="botforge-voice.mp3"',
        },
    )
