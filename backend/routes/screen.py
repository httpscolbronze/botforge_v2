"""Screen analysis: explicit user-supplied screenshot -> local vision model.

The browser never captures anything on its own. The user picks or captures a
screenshot, sees the preview, and presses Analyze, which posts the image here.
"""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.config import settings
from backend.engine.ollama_client import OllamaError, ollama
from backend.engine.policy_engine import build_policy_block, get_policy, preflight_check
from backend.routes.deps import client_id
from backend.storage import repositories

logger = logging.getLogger("botforge.screen")
router = APIRouter(tags=["screen"])

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@router.post("/screen/analyze")
async def analyze_screen(
    image: UploadFile = File(...),
    prompt: str = Form("Describe what is on this screen and point out anything important."),
    client: str = Depends(client_id),
) -> dict:
    policy = get_policy()
    if not policy["screen_analysis"]:
        raise HTTPException(
            status_code=403,
            detail="Screen analysis is disabled by the host AI policy. Ask your administrator.",
        )

    prompt = (prompt or "").strip()[:2000]
    if not prompt:
        raise HTTPException(status_code=400, detail="Describe what you want to know about the screenshot.")
    refusal = preflight_check(prompt, policy)
    if refusal:
        raise HTTPException(status_code=403, detail=refusal)

    content_type = (image.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Screenshot must be a PNG, JPEG or WebP image.",
        )

    raw = await image.read()
    await image.close()
    if not raw:
        raise HTTPException(status_code=400, detail="The screenshot is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Screenshot is larger than 8 MB.")
    if not raw.startswith((b"\x89PNG", b"\xff\xd8", b"RIFF")):
        raise HTTPException(status_code=415, detail="That file does not look like an image.")

    model = repositories.selected_models()["vision_model"]
    system_prompt = (
        f"{build_policy_block(policy)}\n\n"
        "## Screen analysis mode\n"
        "You are analysing a screenshot the user explicitly shared. Describe only what is "
        "visible. Do not guess at text you cannot read. If the image contains credentials, "
        "personal data or other sensitive material, mention that it is present but do not "
        "transcribe it."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt + "\n\nAnswer based only on the attached screenshot."},
    ]
    encoded = base64.b64encode(raw).decode("ascii")

    try:
        answer = await ollama.chat(model, messages, images=[encoded], temperature=0.2)
    except OllamaError as exc:
        detail = exc.message
        if "not installed" in detail.lower():
            detail += f" Screen analysis needs a vision model, e.g. `ollama pull {model}`."
        logger.warning("Screen analysis failed: %s", detail)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc

    logger.info("Screen analysed with %s for workspace %s", model, client)
    return {
        "answer": answer,
        "model": model,
        "policy_enforced": True,
        "processed_locally": True,
        "note": "The screenshot was sent only to your local Ollama server and was not stored.",
    }
