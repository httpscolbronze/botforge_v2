"""Persona -> system prompt composition.

Ordering matters for security: the host policy block is written first and the
persona block is explicitly subordinated to it. Nothing a client sends can
remove or precede the policy block.
"""

from __future__ import annotations

import re
from typing import Any

MAX_FIELD = 600
MAX_INSTRUCTIONS = 2000

DEFAULT_PERSONA: dict[str, str] = {
    "name": "Alex",
    "persona": "Senior Software Engineer",
    "tone": "Professional",
    "response_style": "Detailed and explanatory",
    "expertise": "Python, APIs and System Design",
    "language": "English",
    "additional_instructions": "",
}


def _clean(value: Any, limit: int = MAX_FIELD) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").strip()
    # Collapse absurd whitespace but keep paragraph breaks.
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text[:limit]


def normalise_persona(payload: dict[str, Any] | None) -> dict[str, str]:
    payload = payload or {}
    result: dict[str, str] = {}
    for key, default in DEFAULT_PERSONA.items():
        limit = MAX_INSTRUCTIONS if key == "additional_instructions" else MAX_FIELD
        value = _clean(payload.get(key), limit)
        result[key] = value or (default if key != "additional_instructions" else "")
    return result


def build_persona_block(persona: dict[str, str]) -> str:
    lines = [
        "## Assistant persona (lower priority than host policy)",
        f"- Assistant name: {persona.get('name', 'Assistant')}",
    ]
    optional = {
        "persona": "Role",
        "tone": "Tone",
        "response_style": "Response style",
        "expertise": "Areas of expertise",
        "language": "Reply language",
    }
    for key, label in optional.items():
        value = persona.get(key, "")
        if value:
            lines.append(f"- {label}: {value}")
    if persona.get("additional_instructions"):
        lines.append("")
        lines.append("### Additional user instructions")
        lines.append(persona["additional_instructions"])
    lines.append("")
    lines.append(
        "Stay in character as this assistant, but always obey the host policy above. "
        "If the two conflict, the host policy wins and you should say so briefly."
    )
    return "\n".join(lines)


def build_system_prompt(policy: dict[str, Any], persona: dict[str, str]) -> str:
    """Compose the final system prompt: policy first, persona second."""
    from backend.engine.policy_engine import build_policy_block

    return f"{build_policy_block(policy)}\n\n{build_persona_block(persona)}"
