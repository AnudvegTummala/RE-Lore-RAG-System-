"""Simple file-backed checkpoint for the ingestor.

Tracks completion per (key, phase) pair so each pass (nodes,
relationships, text_embed, image_embed) is independently resumable.
Writes are atomic via .tmp rename.
"""

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_DIR = Path("/data/state")


class IngestCheckpoint:
    def __init__(self, name: str) -> None:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._path = _STATE_DIR / f"{name}.json"
        self._lock = threading.Lock()
        self._state: dict[str, dict[str, bool]] = self._load()

    def is_done(self, key: str, *, phase: str) -> bool:
        with self._lock:
            return self._state.get(key, {}).get(phase, False)

    def mark_done(self, key: str, *, phase: str) -> None:
        with self._lock:
            if key not in self._state:
                self._state[key] = {}
            self._state[key][phase] = True

    def save(self) -> None:
        with self._lock:
            self._flush()

    def _flush(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Could not read checkpoint %s, starting fresh", self._path)
        return {}
