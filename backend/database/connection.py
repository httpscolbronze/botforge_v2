"""SQLite connection, migration runner and transaction helpers.

Design notes:
* One short-lived connection per operation keeps the app safe across FastAPI's
  threadpool and makes the "restore a backup file" flow possible without
  closing borrowed handles.
* WAL mode plus a busy timeout keeps concurrent reads working while a write is
  in flight.
* Migrations are numbered SQL files recorded in ``schema_migrations``. They run
  exactly once; no startup path ever drops or truncates user data.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from backend.config import settings

logger = logging.getLogger("botforge.database")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class DatabaseError(Exception):
    """A storage failure that is safe to surface to the UI."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.db_path)
        self._initialised = False

    # -- connections -------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            connection = sqlite3.connect(
                str(self.path), timeout=15.0, check_same_thread=False
            )
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not open the BotForge database: {exc}") from exc
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Write transaction: commits on success, rolls back on any error."""
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def reader(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    # -- convenience -------------------------------------------------------
    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.reader() as connection:
            return list(connection.execute(sql, params).fetchall())

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.reader() as connection:
            return connection.execute(sql, params).fetchone()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.transaction() as connection:
            cursor = connection.execute(sql, params)
            return int(cursor.lastrowid or 0)

    # -- schema ------------------------------------------------------------
    def initialize(self) -> None:
        """Create the database and apply any pending migrations."""
        if self._initialised:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            applied = {
                row["version"]
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = migration.stem
                if version in applied:
                    continue
                sql = migration.read_text("utf-8")
                try:
                    connection.executescript(sql)
                except sqlite3.Error as exc:
                    raise DatabaseError(
                        f"Database migration {version} failed: {exc}"
                    ) from exc
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, _utc_now()),
                )
                logger.info("Applied database migration %s", version)
        self._initialised = True

    def migrations(self) -> list[dict[str, str]]:
        try:
            rows = self.query(
                "SELECT version, applied_at FROM schema_migrations ORDER BY version"
            )
        except sqlite3.Error:
            return []
        return [dict(row) for row in rows]

    def integrity_check(self) -> str:
        try:
            row = self.query_one("PRAGMA integrity_check")
        except sqlite3.Error as exc:
            return f"unavailable: {exc}"
        return str(row[0]) if row else "unknown"

    def info(self) -> dict[str, Any]:
        size = self.path.stat().st_size if self.path.exists() else 0
        return {
            "engine": "sqlite",
            "path": str(self.path),
            "size_bytes": size,
            "migrations": self.migrations(),
            "integrity": self.integrity_check(),
            "documents_dir": str(settings.documents_dir),
            "backups_dir": str(settings.backups_dir),
        }

    # -- backup primitives -------------------------------------------------
    def backup_to(self, destination: Path) -> Path:
        """Consistent online copy of the database (WAL included)."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.unlink()
        source = self.connect()
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return destination

    def restore_from(self, source: Path) -> None:
        """Replace the live database file after validating the source."""
        if not source.exists():
            raise DatabaseError("The backup database file is missing.", 404)
        try:
            check = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
            try:
                result = check.execute("PRAGMA integrity_check").fetchone()
                tables = {
                    row[0]
                    for row in check.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            finally:
                check.close()
        except sqlite3.Error as exc:
            raise DatabaseError(f"The backup database cannot be read: {exc}", 422) from exc
        if not result or result[0] != "ok":
            raise DatabaseError("The backup failed its integrity check.", 422)
        if "users" not in tables or "app_settings" not in tables:
            raise DatabaseError("That file is not a BotForge database.", 422)

        for suffix in ("-wal", "-shm"):
            stale = Path(str(self.path) + suffix)
            if stale.exists():
                stale.unlink()
        shutil.copy2(source, self.path)
        self._initialised = False
        self.initialize()
        logger.info("Database restored from %s", source)


database = Database()
