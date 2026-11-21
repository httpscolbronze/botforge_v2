"""Database + document backups and safe restore.

A backup is a zip archive under ``data/backups`` containing:
  * ``botforge.db``   consistent SQLite copy (WAL checkpointed)
  * ``documents/``    the original uploaded files
  * ``vectors.json`` embeddings + chunk metadata (rebuilt into Chroma on restore)
  * ``manifest.json`` metadata so a backup can be inspected without restoring

Restore validates the archive, takes a safety snapshot of the current state,
then swaps the database and document files. If the vector directory cannot be
replaced because ChromaDB has open handles, the restore still succeeds for the
authoritative data and reports the vector warning honestly.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.database.connection import DatabaseError, database

logger = logging.getLogger("botforge.backup")

MAX_BACKUPS = 25
NAME_PREFIX = "botforge-"


class BackupError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _safe_relative(base: Path, path: Path) -> str:
    return str(path.relative_to(base)).replace("\\", "/")


def list_backups() -> list[dict[str, Any]]:
    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(settings.backups_dir.glob("*.zip"), reverse=True):
        stat = path.stat()
        manifest: dict[str, Any] = {}
        try:
            with zipfile.ZipFile(path) as archive:
                if "manifest.json" in archive.namelist():
                    manifest = json.loads(archive.read("manifest.json"))
        except (zipfile.BadZipFile, OSError, ValueError):
            manifest = {}
        items.append(
            {
                "id": path.name,
                "created_at": manifest.get("created_at")
                or datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(timespec="milliseconds"),
                "size_bytes": stat.st_size,
                "includes_vectors": bool(manifest.get("includes_vectors")),
                "app_version": manifest.get("app_version"),
            }
        )
    return items


def create_backup(*, include_vectors: bool = True, reason: str = "manual") -> dict[str, Any]:
    settings.ensure_dirs()
    name = f"{NAME_PREFIX}{_timestamp()}.zip"
    destination = settings.backups_dir / name
    if destination.exists():
        destination = settings.backups_dir / f"{_timestamp()}-{len(list_backups()) + 1}.zip"
        destination = settings.backups_dir / f"{NAME_PREFIX}{destination.name}"
    final_name = destination.name

    database.initialize()
    with tempfile.TemporaryDirectory(prefix="botforge-backup-") as temp_dir:
        temp = Path(temp_dir)
        db_copy = temp / "botforge.db"
        database.backup_to(db_copy)

        manifest = {
            "app": settings.app_name,
            "app_version": settings.version,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "reason": reason,
            "includes_vectors": include_vectors,
            "documents": 0,
            "vector_chunks": 0,
            "database_bytes": db_copy.stat().st_size,
        }

        vectors: list[dict[str, Any]] = []
        if include_vectors:
            try:
                from backend.rag.retrieval import vector_store

                vectors = vector_store.export_all()
                manifest["vector_chunks"] = len(vectors)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Could not export vectors for backup: %s", exc)
                manifest["vectors_error"] = str(exc)

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_copy, "botforge.db")
            documents_dir = settings.documents_dir
            if documents_dir.exists():
                for file in documents_dir.rglob("*"):
                    if file.is_file():
                        archive.write(file, _safe_relative(settings.data_dir, file))
                        manifest["documents"] += 1
            if include_vectors and vectors:
                archive.writestr("vectors.json", json.dumps(vectors))
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))

    _prune_backups()
    logger.info("Created backup %s (%s bytes)", final_name, destination.stat().st_size)
    return {"backup": next((b for b in list_backups() if b["id"] == final_name), None)}


def _prune_backups() -> None:
    backups = sorted(
        settings.backups_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for stale in backups[MAX_BACKUPS:]:
        try:
            stale.unlink()
        except OSError:
            pass


def _extract(archive_path: Path, destination: Path) -> list[str]:
    written: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(destination.resolve())
            except ValueError as exc:
                raise BackupError("The backup contains an unsafe file path.", 422) from exc
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            written.append(member.filename)
    return written


def restore_backup(backup_id: str) -> dict[str, Any]:
    archive_path = (settings.backups_dir / backup_id).resolve()
    try:
        archive_path.relative_to(settings.backups_dir.resolve())
    except ValueError as exc:
        raise BackupError("Unknown backup.", 404) from exc
    if not archive_path.exists():
        raise BackupError(f"Backup '{backup_id}' was not found in {settings.backups_dir}.", 404)

    # Always keep a snapshot of the current state before overwriting anything.
    safety = create_backup(include_vectors=False, reason="pre-restore")

    warnings: list[str] = []
    documents_replaced = False
    vectors_replaced = False

    with tempfile.TemporaryDirectory(prefix="botforge-restore-") as temp_dir:
        temp = Path(temp_dir)
        try:
            written = _extract(archive_path, temp)
        except zipfile.BadZipFile as exc:
            raise BackupError("That file is not a readable BotForge backup.", 422) from exc

        if "botforge.db" not in written:
            raise BackupError("The backup does not contain botforge.db.", 422)

        try:
            database.restore_from(temp / "botforge.db")
        except DatabaseError as exc:
            raise BackupError(exc.message, exc.status_code) from exc

        restored_docs = temp / "documents"
        if restored_docs.exists():
            target = settings.documents_dir
            try:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(restored_docs, target)
                documents_replaced = True
            except OSError as exc:
                warnings.append(f"Document files could not be restored: {exc}")
        else:
            warnings.append("The backup has no document files; metadata was restored only.")

        restored_vectors = temp / "vectors.json"
        if restored_vectors.exists():
            try:
                records = json.loads(restored_vectors.read_text("utf-8"))
                from backend.rag.retrieval import vector_store

                vectors_replaced = vector_store.replace_all(records) >= 0
            except Exception as exc:  # pragma: no cover - defensive
                warnings.append(
                    f"Vector data could not be restored: {exc}. "
                    "Re-upload documents to rebuild embeddings."
                )
        else:
            warnings.append("The backup did not include vectors; re-upload documents to rebuild them.")

    logger.warning("Restored backup %s", backup_id)
    return {
        "restored": backup_id,
        "safety_backup": safety.get("backup", {}).get("id"),
        "documents_replaced": documents_replaced,
        "vectors_replaced": vectors_replaced,
        "warnings": warnings,
    }
