"""Text chunking with page metadata preserved for citations."""

from __future__ import annotations

import re
from typing import Any, Iterable

from backend.config import settings


def normalise_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of blank lines but keep paragraph structure.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])", text)
    return [part.strip() for part in parts if part.strip()]


def chunk_text(
    text: str,
    *,
    page: int | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[dict[str, Any]]:
    """Split text into overlapping character chunks, preferring sentence edges."""
    chunk_size = chunk_size or settings.chunk_size
    overlap = settings.chunk_overlap if overlap is None else overlap
    text = normalise_text(text)
    if not text:
        return []

    chunks: list[str] = []
    buffer = ""
    for sentence in _split_sentences(text) or [text]:
        if len(sentence) > chunk_size:
            # Hard-split very long sentences.
            if buffer.strip():
                chunks.append(buffer.strip())
                buffer = ""
            for start in range(0, len(sentence), chunk_size):
                chunks.append(sentence[start : start + chunk_size].strip())
            continue
        if len(buffer) + len(sentence) + 1 <= chunk_size:
            buffer = f"{buffer} {sentence}".strip()
        else:
            if buffer.strip():
                chunks.append(buffer.strip())
            buffer = sentence
    if buffer.strip():
        chunks.append(buffer.strip())

    # Apply overlap by prepending the tail of the previous chunk.
    result: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        if not chunk:
            continue
        if index > 0 and overlap > 0:
            previous_tail = chunks[index - 1][-overlap:]
            chunk = f"{previous_tail} {chunk}".strip()
        result.append({"index": len(result), "text": chunk, "page": page})
    return result


def chunk_pages(pages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    all_chunks: list[dict[str, Any]] = []
    for page in pages:
        for chunk in chunk_text(page.get("text", ""), page=page.get("page")):
            chunk["index"] = len(all_chunks)
            all_chunks.append(chunk)
    return all_chunks
