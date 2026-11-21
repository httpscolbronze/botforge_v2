"""In-memory log ring buffer surfaced in Host Mode -> Logs."""

from __future__ import annotations

import collections
import logging
import threading
from typing import Any


class RingBufferHandler(logging.Handler):
    def __init__(self, capacity: int = 400):
        super().__init__()
        self._buffer: collections.deque[dict[str, Any]] = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - logging internals
        try:
            message = record.getMessage()
            if record.exc_info:
                message += " | " + repr(record.exc_info[1])
            entry = {
                "time": self.formatter.formatTime(record, "%H:%M:%S") if self.formatter else "",
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
            with self._lock:
                self._buffer.append(entry)
        except Exception:
            self.handleError(record)

    def snapshot(self, limit: int = 200, level: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._buffer)
        if level:
            allowed = {
                "DEBUG": 10,
                "INFO": 20,
                "WARNING": 30,
                "ERROR": 40,
                "CRITICAL": 50,
            }
            threshold = allowed.get(level.upper(), 0)
            items = [
                item
                for item in items
                if allowed.get(item["level"], 0) >= threshold
            ]
        return items[-limit:]


LOG_BUFFER = RingBufferHandler()
LOG_BUFFER.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))


def install_logging() -> None:
    root = logging.getLogger()
    if LOG_BUFFER not in root.handlers:
        root.addHandler(LOG_BUFFER)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    # Keep uvicorn's own logger visible in the ring buffer too.
    for name in ("uvicorn", "uvicorn.error", "botforge"):
        logging.getLogger(name).setLevel(logging.INFO)
