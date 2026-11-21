"""Document upload, listing, retrieval queries and deletion.

Original files are kept under ``data/documents``; metadata, ownership and
grants live in SQLite; vectors live in the persistent ChromaDB directory.
Deleting a document removes its vectors, its stored file and its grants.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.config import settings
from backend.engine.policy_engine import get_policy
from backend.rag.chunking import chunk_pages
from backend.rag.embeddings import EmbeddingUnavailable, embed_query, embed_texts
from backend.rag.ingestion import SUPPORTED_EXTENSIONS, IngestionError, extract_pages
from backend.rag.retrieval import vector_store
from backend.routes.deps import client_id
from backend.storage import repositories
from backend.storage.repositories import new_id, utc_now

logger = logging.getLogger("botforge.documents")
router = APIRouter(tags=["documents"])

EMBED_BATCH = 24


def _public(record: dict[str, Any]) -> dict[str, Any]:
    public = {
        key: value
        for key, value in record.items()
        if key not in {"stored_path", "client_id"}
    }
    stored = Path(record.get("stored_path") or "")
    public["file_exists"] = bool(stored and stored.exists())
    if not public["file_exists"]:
        public["warning"] = "The stored file is missing on disk. Delete and re-upload it."
    return public


def _accessible(client: str) -> list[dict[str, Any]]:
    return repositories.list_accessible_documents(client)


@router.get("/documents")
async def list_documents(client: str = Depends(client_id)) -> dict:
    items = _accessible(client)
    missing = [item["id"] for item in items if not Path(item.get("stored_path") or "").exists()]
    return {
        "documents": [_public(item) for item in items],
        "vector_store": vector_store.stats(),
        "document_access": get_policy()["document_access"],
        "missing_files": missing,
    }


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...), client: str = Depends(client_id)
) -> dict:
    policy = get_policy()
    if not policy["document_access"]:
        raise HTTPException(
            status_code=403,
            detail="Document access is disabled by the host AI policy. Ask your administrator.",
        )

    filename = (file.filename or "upload").strip()
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF, DOCX, TXT, CSV or MD file.",
        )

    repositories.ensure_user(client)
    document_id = new_id("doc_")
    destination = settings.documents_dir / f"{document_id}{extension}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    checksum = hashlib.sha256()
    try:
        with destination.open("wb") as handle:
            while True:
                chunk = await file.read(256 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File is larger than the {settings.max_upload_mb} MB limit.",
                    )
                checksum.update(chunk)
                handle.write(chunk)
        await file.close()
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not store the upload: {exc}") from exc

    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        pages = await asyncio.to_thread(extract_pages, destination, extension)
        chunks = await asyncio.to_thread(chunk_pages, pages)
    except IngestionError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # pragma: no cover - defensive
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Extraction failed: {exc}") from exc

    if not chunks:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="No indexable text was found in this file.")

    vectors: list[list[float]] = []
    provider = "unknown"
    embedding_model = None
    warning = None
    try:
        for start in range(0, len(chunks), EMBED_BATCH):
            batch = [chunk["text"] for chunk in chunks[start : start + EMBED_BATCH]]
            result = await embed_texts(batch)
            vectors.extend(result["vectors"])
            provider = result["provider"]
            embedding_model = result["model"]
            warning = warning or result["warning"]
    except EmbeddingUnavailable as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        await asyncio.to_thread(
            vector_store.add_chunks,
            document_id,
            filename,
            chunks,
            vectors,
            client,
        )
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not index document: {exc}") from exc

    record = {
        "id": document_id,
        "client_id": client,
        "name": filename,
        "extension": extension,
        "size_bytes": size,
        "pages": len([p for p in pages if p.get("text")]),
        "chunks": len(chunks),
        "embedding_provider": provider,
        "embedding_model": embedding_model,
        "checksum": checksum.hexdigest(),
        "status": "indexed",
        "created_at": utc_now(),
        "stored_path": str(destination),
    }
    repositories.create_document(record)
    repositories.record_audit(
        client,
        "document.upload",
        target_type="document",
        target_id=document_id,
        detail={
            "name": filename,
            "chunks": len(chunks),
            "embedding_provider": provider,
            "embedding_model": embedding_model,
        },
    )
    logger.info(
        "Indexed '%s' (%s chunks, %s) for workspace %s",
        filename,
        record["chunks"],
        provider,
        client,
    )
    return {
        "document": _public(record),
        "warning": warning,
        "vector_store": vector_store.stats(),
    }


class DocumentQuery(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] | None = None
    k: int | None = Field(default=None, ge=1, le=12)


@router.post("/documents/query")
async def query_documents(payload: DocumentQuery, client: str = Depends(client_id)) -> dict:
    policy = get_policy()
    if not policy["document_access"]:
        raise HTTPException(
            status_code=403,
            detail="Document access is disabled by the host AI policy.",
        )

    own = _accessible(client)
    if not own:
        raise HTTPException(
            status_code=404,
            detail="No documents in this workspace yet. Upload a file first.",
        )

    own_ids = {doc["id"] for doc in own}
    if payload.document_ids:
        requested = [doc_id for doc_id in payload.document_ids if doc_id in own_ids]
        if not requested:
            raise HTTPException(
                status_code=403,
                detail="Those documents are not available in this workspace.",
            )
    else:
        requested = list(own_ids)

    k = min(payload.k or policy["max_context_chunks"], 12)
    try:
        embedding = await embed_query(payload.question)
    except EmbeddingUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    hits = await asyncio.to_thread(
        vector_store.query, embedding["vectors"][0], document_ids=requested, k=k
    )
    repositories.record_audit(
        client,
        "document.query",
        detail={"documents": len(requested), "results": len(hits)},
    )
    return {
        "question": payload.question,
        "results": hits,
        "provider": embedding["provider"],
        "warning": embedding["warning"],
        "vector_store": vector_store.stats(),
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, client: str = Depends(client_id)) -> dict:
    target = repositories.get_document(document_id)
    # Only the owner may delete a document; read grants do not imply management.
    if not target or not repositories.owns_document(client, document_id):
        raise HTTPException(status_code=404, detail="Document not found in this workspace.")

    vector_warning = None
    try:
        await asyncio.to_thread(vector_store.delete_document, document_id)
    except Exception as exc:  # pragma: no cover - defensive
        vector_warning = f"Vectors could not be removed: {exc}"
        logger.warning("Vector cleanup failed for %s: %s", document_id, exc)

    Path(target.get("stored_path") or "").unlink(missing_ok=True)
    repositories.delete_document_record(document_id)
    repositories.record_audit(
        client, "document.delete", target_type="document", target_id=document_id
    )
    logger.info("Deleted document %s", document_id)
    return {
        "deleted": document_id,
        "vectors_removed": vector_warning is None,
        "warning": vector_warning,
        "vector_store": vector_store.stats(),
    }
