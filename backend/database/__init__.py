"""Persistent SQLite storage for BotForge_v2.

The database is the source of truth for users, agents, personas,
conversations, messages, documents, host policies, audit records and
application settings. ChromaDB holds only derived vectors and the original
files live under ``data/documents``.
"""

from backend.database.connection import Database, DatabaseError, database
from backend.database.backup import (
    BackupError,
    create_backup,
    list_backups,
    restore_backup,
)

__all__ = [
    "Database",
    "DatabaseError",
    "database",
    "BackupError",
    "create_backup",
    "list_backups",
    "restore_backup",
]
