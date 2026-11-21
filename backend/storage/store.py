"""Small atomic JSON store used for policies, personas, documents and chats.

The MVP is single-host and single-process, so JSON files plus a lock are
enough. Writes go to a temp file and are atomically replaced so a crash cannot
truncate stored policies or a conversation.
"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable


class JsonStore:
    def __init__(self, path: Path, default: Any):
        self.path = Path(path)
        self._default = default
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(copy.deepcopy(default))

    # -- internals ---------------------------------------------------------
    def _read_unlocked(self) -> Any:
        try:
            return json.loads(self.path.read_text("utf-8"))
        except FileNotFoundError:
            return copy.deepcopy(self._default)
        except (json.JSONDecodeError, OSError):
            # Corrupt file: keep it for inspection and start from defaults.
            try:
                self.path.replace(self.path.with_suffix(self.path.suffix + ".corrupt"))
            except OSError:
                pass
            return copy.deepcopy(self._default)

    def _write(self, data: Any) -> Any:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        os.replace(tmp, self.path)
        return data

    # -- public API --------------------------------------------------------
    def read(self) -> Any:
        with self._lock:
            return self._read_unlocked()

    def write(self, data: Any) -> Any:
        with self._lock:
            return self._write(data)

    def update(self, mutator: Callable[[Any], Any]) -> Any:
        """Mutate the stored value under lock; returns the mutator's result."""
        with self._lock:
            data = self._read_unlocked()
            result = mutator(data)
            self._write(data)
            return result
